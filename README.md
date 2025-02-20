# Grab Status Checker Automation

This repository contains an automated solution for checking the status of Grab merchant outlets and sending daily reports by email.

## How It Works

The automation runs daily at midnight UTC using GitHub Actions. It:

1. Logs into Grab Merchant for each outlet
2. Checks the status of each outlet
3. Compiles results into an Excel spreadsheet
4. Emails the report to specified recipients
5. Saves the report as a GitHub artifact

## Setup Instructions

### Initial Setup

1. **Fork or clone this repository** to your GitHub account
2. **Configure secrets** in your repository:
   - Go to Settings → Secrets and variables → Actions
   - Create the following secrets:
     - `OUTLETS_CSV_CONTENT`: The entire content of your outlets.csv file
     - `SMTP_SERVER`: Your email server (e.g., smtp.gmail.com)
     - `SMTP_PORT`: Your email server port (e.g., 587 or 465)
     - `EMAIL_USERNAME`: Your email username
     - `EMAIL_PASSWORD`: Your email password or app password
     - `EMAIL_RECIPIENT`: The recipient email address
     - `EMAIL_SENDER`: The sender email address
3. **Verify the workflow file** at `.github/workflows/grab_status_check.yml`
4. **Adjust the schedule** if needed (currently set to midnight UTC)

### CSV Format

Your `outlets.csv` should follow this format:

```
outlet_name,username,password
"Outlet 1",user1@example.com,password1
"Outlet 2*",user2@example.com,password2
"Outlet 3**",user3@example.com,password3
```

Special notes:
- Use `*` in the outlet name to select the first outlet
- Use `**` in the outlet name to select the second outlet

### Running Manually

You can trigger the workflow manually:

1. Go to the "Actions" tab in your repository
2. Select the "Daily Grab Status Checker" workflow
3. Click "Run workflow"
4. Confirm by clicking the green "Run workflow" button

## Monitoring and Troubleshooting

### Checking Workflow Status

1. Go to the "Actions" tab to see all workflow runs
2. Click on any run to see detailed logs
3. You can download the Excel report from the "Artifacts" section

### Common Issues and Solutions

- **Login failures**: Verify the username and password in your secrets
- **Timeout errors**: The script might need more time - adjust the `timeout-minutes` in the workflow file
- **Email delivery issues**: Check your SMTP settings and email credentials

## Maintaining the Automation

### Updating Outlet Information

To update outlet information:

1. Update your local CSV file
2. Go to your repository secrets
3. Update the `OUTLETS_CSV_CONTENT` secret with the new CSV content

### Adjusting the Schedule

Edit the `.github/workflows/grab_status_check.yml` file and change the cron expression:

```yaml
on:
  schedule:
    - cron: '0 8 * * *'  # This would run at 8 AM UTC
```

## Security Considerations

- Never commit credentials directly to the repository
- The workflow uses repository secrets which are encrypted
- Consider rotating passwords periodically for better security

## Limitations

- GitHub Actions has a maximum runtime of 6 hours per job
- Free accounts are limited to 2,000 minutes/month for private repositories

---

Created and maintained by [Your Name]