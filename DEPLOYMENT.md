# 🚀 Deployment Guide

## Deploy to Vercel via GitHub

### Prerequisites
- GitHub account
- Vercel account
- Your code pushed to a GitHub repository

### Step 1: Push to GitHub

1. Initialize git if not already done:
```bash
git init
git add .
git commit -m "Initial commit: Nutritional Chatbot"
```

2. Create a new repository on GitHub and push:
```bash
git remote add origin https://github.com/yourusername/nutritional-chatbot.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Vercel

1. **Import Project on Vercel:**
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New..." → "Project"
   - Import your GitHub repository

2. **Configure Project:**
   - Framework Preset: Python
   - Root Directory: ./
   - Build Command: Leave empty (Vercel will detect)
   - Output Directory: public
   - Install Command: `pip install -r requirements.txt`

3. **Environment Variables:**
   - No required environment variables for basic functionality
   - PYTHON_VERSION: 3.9 (automatically set)

4. **Deploy:**
   - Click "Deploy"
   - Your app will be live at `https://your-project-name.vercel.app`

### Step 3: Automatic Deployments

The GitHub Actions workflow (`.github/workflows/deploy.yml`) will automatically deploy:
- On every push to `main` branch
- On pull requests to `main`

### 🌐 Access Your Live Chatbot

Once deployed, your nutritional chatbot will be available at:
- Primary URL: `https://your-project-name.vercel.app`
- API Endpoint: `https://your-project-name.vercel.app/api/chat`

### 📱 Features Available

- **Nutritional Information**: Calories, protein, carbs, fats for Indian foods
- **Ayurvedic Properties**: Rasa, virya, guna, vipaka, dosha effects
- **Multilingual Support**: English and Hindi
- **Voice Input**: Speech-to-text functionality
- **Smart Suggestions**: Quick access to common nutritional queries
- **Source Citations**: See the knowledge base sources for each response

### 🔧 Customization

#### Adding New Foods
1. Update `knowledge_base.csv` with new food items
2. Re-run the training script: `python train_chat_model.py`
3. Commit and push changes

#### Modifying Responses
Edit the main chat logic in `app.py` to customize:
- Response generation
- Search algorithms
- Conversation flow

### 📊 Monitoring

Vercel provides built-in analytics for:
- Page views
- API usage
- Performance metrics
- Error logs

### 🆘 Troubleshooting

**Common Issues:**
1. **Build Failures**: Check Python version compatibility
2. **API Errors**: Verify knowledge base files are present
3. **Slow Responses**: Consider optimizing embeddings cache

**Debug Mode:**
Add `?debug=true` to your URL to see detailed error messages.

### 📝 API Usage

Your deployed chatbot can also be used via API:

```javascript
const response = await fetch('https://your-project-name.vercel.app/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What are the benefits of moong dal?",
    lang: "en"
  })
});
const data = await response.json();
console.log(data.response);
```

### 🎯 Next Steps

1. **Custom Domain**: Add your custom domain in Vercel dashboard
2. **Analytics**: Set up Google Analytics for usage tracking
3. **SEO**: Optimize meta tags and descriptions
4. **Performance**: Monitor and optimize loading times

---

**🎉 Congratulations!** Your nutritional chatbot is now live and accessible to users worldwide!
