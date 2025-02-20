from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
import logging
from multiprocessing import Pool, Manager
from datetime import datetime
# New imports for email functionality
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('grab_status_checker')

# Record start time
start_time = time.time()

# Determine environment and set ChromeDriver path
is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
if is_github_actions:
    chrome_driver_path = "/usr/local/bin/chromedriver"
    logger.info(f"Running in GitHub Actions environment")
else:
    chrome_driver_path = "C:/Users/Jaden/Desktop/FpBot/chromedriver.exe"
    logger.info(f"Running in local environment")

# Define function to process a single outlet with retries
def check_outlet_status(outlet_name, username, password, return_list):
    """Login to Grab Merchant and get outlet status with retry mechanism"""
    logger.info(f"Checking status for {outlet_name}...")
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        # Setup Chrome options - always use headless mode
        service = Service(chrome_driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)  # Set page load timeout
        
        try:
            logger.info(f"Attempt {attempt+1} for {outlet_name}")
            driver.get("https://merchant.grab.com/login")
            wait = WebDriverWait(driver, 20)  # Increased wait time for GitHub Actions
            
            # Input username
            username_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
            username_input.clear()
            username_input.send_keys(username)
            logger.info(f"Entered username for {outlet_name}")
            
            # Input password
            password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
            password_input.clear()
            password_input.send_keys(password)
            logger.info(f"Entered password for {outlet_name}")
            
            # Click submit button
            submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//form/div/button')))
            submit_button.click()
            logger.info(f"Clicked submit button for {outlet_name}")
            
            # Handle possible popups
            try:
                continue_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable(
                    (By.XPATH, '/html/body/div[2]/div/div[2]/div/div[2]/div/div/div/div[2]/button[2]')
                ))
                continue_button.click()
                logger.info(f"Clicked 'Continue' button for {outlet_name}")
            except Exception as e:
                logger.info(f"No 'Continue' button found for {outlet_name}, skipping")
            
            try:
                close_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable(
                    (By.XPATH, '/html/body/div[2]/div/div[2]/div/div[2]/div/div/div/div[3]/button[1]')
                ))
                close_button.click()
                logger.info(f"Clicked 'Close' button for {outlet_name}")
            except Exception as e:
                logger.info(f"No 'Close' button found for {outlet_name}, skipping")
            
            # Navigate to Orders page
            driver.get("https://merchant.grab.com/order")
            logger.info(f"Navigated to Orders page for {outlet_name}")
            
            # Check if outlet selection is needed
            outlet_path = None
            if "**" in outlet_name:
                outlet_path = "/html/body/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/table/tbody/tr[3]/td[1]/div/span[1]"
                logger.info(f"Will select second outlet for {outlet_name}")
            elif "*" in outlet_name:
                outlet_path = "/html/body/div/div/div/div[2]/div/div[2]/div/div[2]/div/div/div/div/div/div[2]/table/tbody/tr[2]/td[1]/div/span[1]"
                logger.info(f"Will select first outlet for {outlet_name}")
            
            if outlet_path:
                try:
                    # Scroll to make outlet visible
                    element = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, outlet_path)))
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    
                    # Click the outlet
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, outlet_path))).click()
                    logger.info(f"Successfully clicked outlet for {outlet_name}")
                except Exception as e:
                    logger.warning(f"Could not click outlet for {outlet_name}: {e}")
                    if attempt == max_retries - 1:
                        return_list.append([outlet_name, "Could not select outlet", username])
                        driver.quit()
                        return
                    else:
                        driver.quit()
                        time.sleep(retry_delay)
                        continue
            
            # Get status
            try:
                status_span = WebDriverWait(driver, 15).until(EC.visibility_of_element_located(
                    (By.XPATH, "/html/body/div[1]/div/div/div[2]/div/div[1]/div[2]/button/span")
                ))
                outlet_status = status_span.text.strip()
                logger.info(f"✅ {outlet_name} status: {outlet_status}")
                return_list.append([outlet_name, outlet_status, username])
                driver.quit()
                return
            except Exception as e:
                logger.warning(f"Could not get status for {outlet_name} on attempt {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All attempts failed for {outlet_name}")
                    return_list.append([outlet_name, "Status check failed", username])
        except Exception as e:
            logger.warning(f"Error processing {outlet_name} on attempt {attempt+1}: {e}")
        finally:
            try:
                driver.quit()
                logger.info(f"Closed browser for {outlet_name}")
            except:
                pass
            
        # Wait before retry if not the last attempt
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

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
    receiver_emails = ["your1@hotmail.com", "your2@gmail.com"]
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

# Main execution logic with timeout handling and email functionality
def main():
    max_runtime_seconds = 25 * 60  # 25 minutes maximum runtime
    logger.info(f"Starting Grab status checker with {max_runtime_seconds}s max runtime")
    excel_file = "outlet_status.xlsx"
    email_sent = False

    try:
        # Read outlet data
        outlet_data = pd.read_csv("outlets.csv")
        outlet_count = len(outlet_data)
        logger.info(f"Loaded {outlet_count} outlets from CSV")
        
        # Set up multiprocessing
        manager = Manager()
        return_list = manager.list()
        max_processes = min(5, outlet_count)  # Use at most 5 processes
        
        # Calculate time per outlet to ensure we finish within timeout
        time_per_outlet = max_runtime_seconds * 0.9 / outlet_count
        logger.info(f"Allocating ~{time_per_outlet:.1f} seconds per outlet")
        
        with Pool(max_processes) as pool:
            # Start the tasks
            results = []
            for _, row in outlet_data.iterrows():
                results.append(pool.apply_async(
                    check_outlet_status, 
                    (row["outlet_name"], row["username"], row["password"], return_list)
                ))
            
            # Wait for results with timeout monitoring
            remaining_time = max_runtime_seconds - (time.time() - start_time)
            for result in results:
                try:
                    # Wait with timeout to ensure we don't go over max runtime
                    result.get(timeout=remaining_time / len(results))
                except Exception as e:
                    logger.error(f"Task timed out or failed: {e}")
                
                # Recalculate remaining time
                remaining_time = max_runtime_seconds - (time.time() - start_time)
                if remaining_time <= 0:
                    logger.warning("Maximum runtime reached, stopping further processing")
                    break
        
        # Prepare and save results
        results_count = len(return_list)
        logger.info(f"Processing complete. Got status for {results_count}/{outlet_count} outlets")
        
        if results_count > 0:
            # Convert results to DataFrame
            df = pd.DataFrame(list(return_list), columns=["Outlet Name", "Status", "Username"])
            
            # Add timestamp column
            df["Check Time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Save to Excel
            df.to_excel(excel_file, index=False)
            logger.info(f"Results saved to {excel_file}")
            
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
        else:
            logger.error("No results were collected! Skipping file generation and email.")
    
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise
    
    finally:
        # Calculate total runtime
        elapsed_time = time.time() - start_time
        logger.info(f"Total runtime: {elapsed_time:.2f} seconds")
        logger.info(f"Email status: {'Sent' if email_sent else 'Not sent'}")

if __name__ == "__main__":
    main()