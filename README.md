# Gmail Insights MCP Server

An MCP (Model Context Protocol) server that provides intelligent insights about your Gmail inbox. This server can analyze your emails, identify important messages you might have missed, provide summaries by sender, and much more.

## Features

- 📧 **Unread Email Analysis**: Get your unread emails sorted by importance
- 🎯 **Missed Important Emails**: Find high-priority emails you might have overlooked
- 📊 **Sender Analytics**: Get summaries of your emails grouped by sender
- 🔍 **Advanced Search**: Use Gmail's powerful search syntax
- 📈 **Weekly Insights**: Comprehensive weekly email overview
- 🤖 **Smart Importance Scoring**: AI-powered email importance calculation

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up Gmail API Credentials

1. **Go to Google Cloud Console**: Visit [Google Cloud Console](https://console.cloud.google.com/)

2. **Create/Select Project**: Create a new project or select an existing one

3. **Enable APIs**:
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API" and click "Enable"
   - Search for "Calendar API" and click "Enable"

4. **Create Credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Desktop application"
   - **Important**: In the "Authorized redirect URIs" section, add these URIs:
     ```
     http://localhost:8080/
     http://localhost:8081/
     ```
   - Download the JSON file and rename it to `credentials.json`

5. **Place Credentials**: Put the `credentials.json` file in the same directory as `gmail_server.py`

### 3. First Run Authentication

Make sure the claude_desktop_configuration looks like this:
```
{
  "mcpServers": {
    "MP_Server": {
      "command": "/Users/shreyas/anaconda3/envs/mcp-server/bin/mcp",
      "args": [
        "run",
        "/Users/shreyas/tempDesktop/Programming/GeneralPurposeMCP/mp_server.py"
      ]
    }
  }
}
```

```bash
mcp install mp_server.py
```

On first run, the server will:
- Open your web browser
- Ask you to sign in to your Google account
- Request permission to read your Gmail
- Save authentication tokens for future use

## Available Tools

### `get_unread_emails(max_results=20)`
Returns your unread emails sorted by importance score.

### `get_important_missed_emails(days_back=7, importance_threshold=7)`
Finds important emails (score ≥ 7) from the last N days that you haven't read yet.

### `get_email_summary_by_sender(days_back=30)`
Provides analytics grouped by sender including:
- Total emails per sender
- Unread count
- Average importance score
- Latest email date

### `search_emails(query, max_results=20)`
Search emails using Gmail's search syntax:
- `from:sender@example.com` - Emails from specific sender
- `subject:meeting` - Emails containing "meeting" in subject
- `has:attachment` - Emails with attachments
- `is:important` - Gmail-marked important emails
- `newer_than:3d` - Emails from last 3 days

### `get_weekly_email_insights()`
Comprehensive weekly overview including:
- Total emails and unread count
- High importance email count
- Daily breakdown
- Top 5 unread important emails

## Importance Scoring Algorithm

The server uses a smart algorithm to score email importance (1-10):

**Base Score**: 5

**Increases Score**:
- Important keywords in subject (+2): urgent, asap, important, critical, deadline, meeting, interview, offer, invoice, payment, security, alert
- Gmail "Important" label (+3)
- Personal category (+1)
- Known important domains (+2)

**Decreases Score**:
- Social category (-1)
- Promotional category (-2)
- No-reply senders (-1)

## Usage Examples

### Basic Usage
```python
# Get your most important unread emails
unread = get_unread_emails(10)

# Find important emails you missed this week
missed = get_important_missed_emails(days_back=7, importance_threshold=8)

# Get weekly insights
insights = get_weekly_email_insights()
```

### Advanced Searches
```python
# Find all emails from your boss with attachments
boss_emails = search_emails("from:boss@company.com has:attachment")

# Find meeting invitations from last week
meetings = search_emails("subject:meeting newer_than:7d")

# Find unread important emails
important_unread = search_emails("is:unread is:important")
```

## Customization

You can customize the importance scoring algorithm by modifying the `_calculate_importance` method in the `GmailClient` class. Adjust:

- Important keywords list
- Domain scoring
- Label weight adjustments
- Base scoring logic

## Security & Privacy

- **Read-Only Access**: The server only requests read-only access to your Gmail
- **Local Storage**: All credentials are stored locally on your machine
- **No Data Transmission**: Your email data is never sent to external servers
- **OAuth 2.0**: Uses Google's secure authentication

## Troubleshooting

### "credentials.json not found"
Make sure you've downloaded the OAuth credentials from Google Cloud Console and placed them in the correct directory.

### Authentication Issues
Delete `token.pickle` file and re-run the server to re-authenticate.

### API Quotas
Gmail API has usage limits. If you hit them:
- Reduce `max_results` parameters
- Space out your requests
- Consider upgrading your Google Cloud quota

## Contributing

Feel free to contribute by:
- Adding new email analysis features
- Improving the importance scoring algorithm
- Adding support for Gmail write operations
- Creating better search and filtering tools

## License

MIT License - feel free to use and modify as needed. 