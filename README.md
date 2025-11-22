# Jersey Travel Agency - Luxury Corporate Travel Website

Premium corporate travel management website for Jersey Travel Agency (Gustova Turizm).

## 🚀 Quick Deploy to Vercel

### Method 1: Vercel Dashboard (EASIEST - 5 minutes)

1. **Go to** [vercel.com](https://vercel.com)
2. **Sign up** with GitHub, GitLab, or email
3. **Click** "Add New Project"
4. **Choose** "Import Third-Party Git Repository" OR "Upload Files"
5. **Upload** the following files:
   - `index.html`
   - `vercel.json`
6. **Click** "Deploy"
7. **Done!** Your site will be live at: `https://your-project-name.vercel.app`

### Method 2: Vercel CLI (For Developers)

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to project folder
cd /path/to/jersey-travel

# Deploy
vercel

# Follow prompts and done!
```

## 📁 Project Structure

```
jersey-travel/
├── index.html          # Main website file
├── vercel.json         # Vercel configuration
└── README.md           # This file
```

## 🔧 Configuration Needed

### 1. Formspree Setup (Contact Form)

1. Go to [formspree.io](https://formspree.io)
2. Sign up with your email: `info@gustovaturizm.com`
3. Create a new form
4. Copy your Form ID (looks like: `xyzabc123`)
5. In `index.html`, find line ~1542:
   ```html
   <form action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
   ```
6. Replace `YOUR_FORM_ID` with your actual Form ID

### 2. Custom Domain (Optional)

After deployment on Vercel:
1. Go to Project Settings → Domains
2. Add your domain: `jerseytravelagency.com`
3. Follow DNS instructions (add A record or CNAME)
4. Wait for DNS propagation (10-30 minutes)
5. Done! Your site will be live at your custom domain

## 📞 Contact Information

- **Phone:** +90 532 309 6001
- **Email:** info@gustovaturizm.com
- **WhatsApp:** +90 532 309 6001
- **Address:** DMN PLAZA, 3rd Floor, 34518 ESENYURT, ISTANBUL, TÜRKIYE
- **TÜRSAB Member:** 18492
- **Tax ID:** 4121218415

## 🎨 Design Features

- **Colors:** Navy (#1B2845) & Gold (#C9A96E) - Premium luxury palette
- **Typography:** Playfair Display (headings) + Lato (body)
- **Fully Responsive:** Mobile, tablet, desktop optimized
- **Animations:** Smooth scrolling, fade-in effects, parallax hero
- **Performance:** Optimized for fast loading

## 🛠️ Technologies Used

- HTML5
- CSS3 (Custom luxury design)
- Vanilla JavaScript
- Google Fonts (Playfair Display, Lato)
- Formspree (Contact form)

## 📈 Future Enhancements

Planned integrations:
- [ ] Next.js migration
- [ ] Amadeus Flight API
- [ ] OpenAI chatbot
- [ ] WhatsApp Business API
- [ ] Supabase database
- [ ] Real-time pricing

## 📄 License

© 2025 Jersey Travel Agency - Gustova Turizm Tic. Ltd. Şti.
All rights reserved.

## 💡 Support

For technical support or questions:
- Email: info@gustovaturizm.com
- Phone: +90 532 309 6001
