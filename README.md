# ShillEarn Hub

A professional, mobile-friendly web platform that operates as an online earning and digital marketing portal for Kenyan users.

## Features

### User Registration & Dashboard
- Free account creation
- Annual paid membership in Kenyan shillings to access earning features
- Secure login system with OTP verification

### Membership Tiers (all in KES)
- Basic – KSh 3,500/year – 1 daily mission – Up to 3 referral levels
- Plus – KSh 10,500/year – 3 daily missions – Up to 3 referral levels
- Pro – KSh 14,000/year – 4 daily missions – Up to 4 referral levels
- Prime – KSh 35,000/year – 10 daily missions – Up to 4 referral levels
- Advanced – KSh 70,000/year – 20 daily missions – Up to 4 referral levels
- Max – KSh 150,000/year – 40 daily missions – Up to 5 referral levels

### Daily Missions System
- Missions involve interacting with client campaigns (e.g., watching ads, engaging with social posts, or completing surveys)
- Automated tracking of completion and crediting of earnings in KES

### Referral Program
- Multi-level structure with real-time tracking of referrals and commissions
- Display earnings breakdown per referral level

### Wallet & Withdrawals
- Built-in KES wallet
- Withdraw via M-Pesa, bank transfer, or PayPal
- Minimum withdrawal limit adjustable by admin

### Admin Panel
- Manage user accounts, campaigns, memberships, payments, and referrals
- Analytics dashboard with charts for earnings and user growth

### Security & Compliance
- Encrypted payments and user data storage
- Terms & Conditions plus Privacy Policy tailored for Kenyan law

### Design & Branding
- Modern, trust-building design with Kenyan cultural colour palette (greens, blacks, reds, and earthy tones)
- Mobile-first UX

### Extras
- Blog/news section for platform updates
- Contact/Help desk with live chat support

## Project Structure

```
shillearnhub/
├── backend/              # Flask application
│   ├── app/              # Application package
│   │   ├── __init__.py   # Initialize Flask app
│   │   ├── models.py     # Database models
│   │   ├── routes.py     # API routes
│   │   └── utils.py      # Utility functions
│   ├── migrations/       # Database migrations
│   ├── tests/            # Unit tests
│   ├── config.py         # Configuration settings
│   ├── requirements.txt  # Python dependencies
│   └── run.py            # Application entry point
└── frontend/            # React application
    ├── public/           # Static files
    ├── src/              # Source code
    │   ├── components/   # React components
    │   ├── pages/        # Page components
    │   ├── services/     # API services
    │   ├── styles/       # CSS styles
    │   ├── utils/        # Utility functions
    │   ├── App.js        # Main component
    │   └── index.js      # Entry point
    ├── package.json      # Node.js dependencies
    └── README.md         # Frontend documentation
```

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 14+
- PostgreSQL

### Installation

1. Clone the repository
2. Set up the backend:
   ```bash
   cd shillearnhub/backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python run.py
   ```
3. Set up the frontend:
   ```bash
   cd shillearnhub/frontend
   npm install
   npm start
   ```

## License

This project is proprietary and confidential.