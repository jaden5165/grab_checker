from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
from multiprocessing import Pool, Manager
import os
import logging
# New imports for email functionality
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('grab_status_checker')

start_time = time.time()  # 记录开始时间

# Determine environment and set ChromeDriver path
is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
if is_github_actions:
    chrome_driver_path = "/usr/local/bin/chromedriver"
    logger.info(f"Running in GitHub Actions environment")
else:
    chrome_driver_path = "C:/Users/Jaden/Desktop/FpBot/chromedriver.exe"
    logger.info(f"Running in local environment")


# **读取门店账号信息**
outlet_data = pd.read_csv("outlets.csv")

# **定义函数：处理单个门店**
def check_outlet_status(outlet_name, username, password, return_list):
    """ 登录 Grab Merchant 并获取门店状态 """
    print(f"🔄 正在检查 {outlet_name}...")

    # **设置 ChromeDriver**
    service = Service(chrome_driver_path)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")

    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://merchant.grab.com/login")
        wait = WebDriverWait(driver, 15)

        # **输入用户名**
        username_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username_input.send_keys(username)

        # **输入密码**
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_input.send_keys(password)

        # **点击提交按钮**
        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//form/div/button')))
        submit_button.click()

        # **处理弹窗**
        try:
            continue_button = WebDriverWait(driver, 2).until(EC.element_to_be_clickable(
                (By.XPATH, '/html/body/div[2]/div/div[2]/div/div[2]/div/div/div/div[2]/button[2]')
            ))
            continue_button.click()
            print("✅ 已点击 'Continue' 按钮")
        except:
            print("⚠️ 没有 'Continue' 按钮，跳过")

        try:
            close_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                (By.XPATH, '/html/body/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/button[1]')
            ))
            close_button.click()
            print("✅ 已点击 'Close' 按钮")
        except:
            print("⚠️ 没有 'Close' 按钮，跳过")

        # **进入 Orders 页面**
        driver.get("https://merchant.grab.com/order")

        # **检查是否需要点击 `Outlet`**
        outlet_path = None

        if "**" in outlet_name:
            outlet_path = "/html/body/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/table/tbody/tr[3]/td[1]/div/span[1]"
            print("🔄 检测到 `**`，点击第二个 Outlet")
        elif "*" in outlet_name:
            outlet_path = "/html/body/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/table/tbody/tr[2]/td[1]/div/span[1]"
            print("🔄 检测到 `*`，点击第一个 Outlet")
        
        if outlet_path:
            try:
                # **滚动页面，使 `Outlet` 可见**
                driver.execute_script("arguments[0].scrollIntoView();", 
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, outlet_path)))
                )

                # **等待 `Outlet` 可点击**
                selected_outlet = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, outlet_path))
                )
                selected_outlet.click()
                print(f"✅ 成功点击 {outlet_name} 的 Outlet")

            except Exception as e:
                print(f"⚠️ 无法点击 Outlet: {e}")
                driver.quit()
                return_list.append([outlet_name, "Unknown", username])
                return

        try:
            # **获取 `Status`**
            status_span = WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                (By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div[1]/div[2]/button/span")
            ))
            outlet_status = status_span.text.strip()
            print(f"✅ {outlet_name} 状态: {outlet_status}")
            return_list.append([outlet_name, outlet_status, username])

        except Exception as e:
            print(f"⚠️ 无法获取 {outlet_name} 状态: {e}")
            return_list.append([outlet_name, "Unknown", username])

    finally:
        driver.quit()
        print(f"✅ 已关闭 Chrome，完成 {outlet_name} 处理\n")

# New function to create HTML email body
def create_email_body(df):
    """
    Create a formatted HTML email body with summary statistics
    
    Args:
        df: DataFrame containing the results
        
    Returns:
        HTML formatted email body
    """
    # Calculate summary statistics
    total_outlets = len(df)
    status_counts = df["Status"].value_counts().to_dict()
    
    # Determine if any outlets are offline or have issues
    offline_outlets = df[df["Status"].str.lower().isin(["offline", "closed", "status check failed"])]
    has_offline = len(offline_outlets) > 0
    
    # Create HTML table for offline outlets if any
    offline_table = ""
    if has_offline:
        offline_table = "<h3>⚠️ Outlets Requiring Attention:</h3>\n<table border='1' cellpadding='5' style='border-collapse: collapse;'>\n"
        offline_table += "<tr><th>Outlet Name</th><th>Status</th><th>Username</th></tr>\n"
        
        for _, row in offline_outlets.iterrows():
            offline_table += f"<tr><td>{row['Outlet Name']}</td><td>{row['Status']}</td><td>{row['Username']}</td></tr>\n"
        
        offline_table += "</table>\n"
    
    # Create the email body
    html = f"""
    <html>
    <body>
        <h2>Grab Outlet Status Report</h2>
        <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h3>Summary:</h3>
        <ul>
            <li>Total outlets checked: {total_outlets}</li>
            {''.join(f'<li>{status}: {count} outlets</li>' for status, count in status_counts.items())}
        </ul>
        
        {offline_table}
        
        <p>The complete report is attached as an Excel file.</p>
        
        <p>
        <i>This is an automated message from the Grab Status Checker.<br>
        Total runtime: {time.time() - start_time:.2f} seconds</i>
        </p>
    </body>
    </html>
    """
    
    return html

# New function to send email with the status report
def send_status_email(results_df, excel_file_path):
    """
    Send email with outlet status report and Excel attachment
    
    Args:
        results_df: DataFrame containing the results
        excel_file_path: Path to the generated Excel file
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    logger.info("Preparing to send status email report...")
    
    # Check if file exists before attempting to send
    if not os.path.exists(excel_file_path):
        logger.error(f"Excel file {excel_file_path} not found. Cannot send email.")
        return False
    
    # Email configuration - will be moved to GitHub Secrets later
    sender_email = os.environ.get("EMAIL_SENDER", "youremail@gmail.com")
    sender_password = os.environ.get("EMAIL_PASSWORD", "yourpass")
    receiver_emails = os.environ.get("EMAIL_RECIPIENT", "your1@hotmail.com,your2@gmail.com").split(",")
    smtp_server = os.environ.get("SMTP_SERVER", "youremail@gmail.com")
    smtp_port = os.environ.get("SMTP_PORT", "456")
    
    # Create email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = ', '.join(receiver_emails)
    msg['Subject'] = f"Grab Outlet Status Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Create email body with summary statistics
    body = create_email_body(results_df)
    msg.attach(MIMEText(body, 'html'))
    
    # Attach the Excel file
    with open(excel_file_path, 'rb') as f:
        attachment = MIMEApplication(f.read(), _subtype='xlsx')
        attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(excel_file_path))
        msg.attach(attachment)
    
    # Send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Encrypt the connection
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        logger.info("Status email sent successfully to: " + ", ".join(receiver_emails))
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False



# **多进程处理所有门店**
if __name__ == '__main__':
    manager = Manager()
    return_list = manager.list()  # 共享变量，存储状态结果
    max_processes = 5  # 并行进程数量

    try:
        with Pool(max_processes) as pool:
            pool.starmap(check_outlet_status, [(row["outlet_name"], row["username"], row["password"], return_list) for _, row in outlet_data.iterrows()])

        # **确保所有数据都存入 Excel**
        df = pd.DataFrame(list(return_list), columns=["Outlet Name", "Status", "Username"])
        excel_file = "outlet_status.xlsx"
        df.to_excel(excel_file, index=False)
        print(f"✅ 所有数据已存入 {excel_file}")
    
        # Create a summary
        status_counts = df["Status"].value_counts()
        logger.info(f"Status summary: {status_counts.to_dict()}")
        
        # Send email with the results - only if file was generated
        if os.path.exists(excel_file):
            email_sent = send_status_email(df, excel_file)
            if email_sent:
                logger.info("Email notification sent successfully")
            else:
                logger.warning("Failed to send email notification")
        else:
            logger.error(f"Excel file {excel_file} was not created. Skipping email.")  
    except Exception as e:
        print(f"⚠️ 处理失败: {e}")

    # **计算总用时**
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"✅ 总用时: {elapsed_time:.2f} 秒")
    logger.info(f"Email status: {'Sent' if email_sent else 'Not sent'}")

