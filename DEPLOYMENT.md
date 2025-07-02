# 🚀 AI Research Assistant - Render Deployment Guide

## 📋 Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com)
2. **GitHub Repository**: Push this code to your GitHub repository
3. **API Keys**: Obtain the required API keys (see below)

## 🔑 Required API Keys

### Essential (at least one LLM provider required):
- **OpenAI API Key**: https://platform.openai.com/api-keys
- **DeepSeek API Key**: https://platform.deepseek.com/ (recommended - very affordable)
- **Anthropic API Key**: https://console.anthropic.com/ (optional fallback)

### Required for Web Search:
- **Tavily API Key**: https://tavily.com/ (web search functionality)

### Optional:
- **Google Translate API Key**: https://cloud.google.com/translate (enhanced translation)

## 🛠 Render Deployment Steps

### 1. Create New Web Service
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New"** → **"Web Service"**
3. Connect your GitHub repository
4. Select your `python-agents` repository

### 2. Configure Build Settings
```
Build Command: pip install -r requirements.txt
Start Command: gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app
```

### 3. Set Environment Variables
In Render dashboard, add these environment variables:

#### Required Variables:
```
OPENAI_API_KEY=your_openai_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
TAVILY_API_KEY=your_tavily_key_here
SECRET_KEY=your_random_secret_key_here
```

#### Optional Variables:
```
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_TRANSLATE_API_KEY=your_google_translate_key_here
```

### 4. Advanced Settings
```
Runtime: Python 3.12.3
Health Check Path: /health
Auto-Deploy: Yes
```

## 🔧 Configuration Details

### Service Configuration:
- **Region**: Choose closest to your users (Oregon, Frankfurt, Singapore)
- **Plan**: Starter ($7/month) recommended for testing
- **Auto-scaling**: Enabled by default

### Security Features:
- ✅ HTTPS enforced
- ✅ CSRF protection enabled
- ✅ Secure session cookies
- ✅ CORS configured for production

### Performance Optimizations:
- ✅ Gunicorn with 2 workers
- ✅ 120-second timeout for long research requests
- ✅ Health check endpoint for monitoring
- ✅ Rate limiting and request queuing

## 🌍 Multi-Language Support

### Supported Languages (12 Indo-European):
- English, Slovenian, German, French, Spanish
- Italian, Portuguese, Russian, Dutch
- Serbian, Macedonian, Croatian

### Translation Features:
- Automatic language detection
- Research conducted in English (best source coverage)
- Results translated to target language
- Bilingual report generation

## 📊 Provider Fallback System

### Smart Fallback Chain:
1. **Primary**: OpenAI (proven performance)
2. **Fallback**: DeepSeek (ultra-low cost ~$0.14/1M tokens)
3. **Final**: Anthropic (premium quality)

### Cost Optimization:
- DeepSeek is ~50-100x cheaper than OpenAI
- Automatic fallback prevents service interruption
- Rate limiting prevents quota exhaustion

## 🔍 Testing Your Deployment

### 1. Health Check
Visit: `https://your-app.onrender.com/health`
Should return JSON with system status.

### 2. Basic Functionality Test
1. Go to your app URL
2. Submit a research request in English
3. Monitor progress page for completion

### 3. Multi-Language Test
1. Submit research in Slovenian or Serbian
2. Verify translation features work
3. Check for bilingual results

## 🐛 Troubleshooting

### Common Issues:

#### Build Failures:
- Check `requirements.txt` is present
- Verify Python version in `runtime.txt`
- Check build logs for missing dependencies

#### Runtime Errors:
- Verify all environment variables are set
- Check service logs for specific errors
- Ensure API keys are valid and have quota

#### Slow Performance:
- Consider upgrading to higher plan
- Monitor resource usage in dashboard
- Check for rate limiting in logs

### Debug Commands:
```bash
# View logs
render logs --service your-service-name

# Check service status
render services list
```

## 📈 Monitoring & Scaling

### Available Metrics:
- Request count and response times
- Memory and CPU usage
- Error rates and health checks

### Scaling Options:
- **Horizontal**: Multiple instances (Professional plan)
- **Vertical**: Larger instance sizes
- **Auto-scaling**: Based on CPU/memory usage

## 💰 Cost Estimates

### Render Hosting:
- **Starter Plan**: $7/month (512MB RAM, 0.5 CPU)
- **Standard Plan**: $25/month (2GB RAM, 1 CPU)

### API Costs (per 1M tokens):
- **DeepSeek**: ~$0.14 (ultra-cheap!)
- **OpenAI GPT-4**: ~$10-30
- **Anthropic Claude**: ~$15-75

### Total Monthly Cost Estimate:
- **Light Usage**: $10-20/month (Render + DeepSeek)
- **Heavy Usage**: $50-100/month (with OpenAI fallback)

## 🎯 Next Steps After Deployment

1. **Test thoroughly** with different languages
2. **Monitor performance** and costs
3. **Set up alerts** for service health
4. **Consider Redis** for scaling (if needed)
5. **Add analytics** for usage tracking

## 📞 Support

- **Render Support**: https://render.com/docs
- **API Issues**: Check respective provider documentation
- **App Issues**: Check service logs and health endpoints

---

🚀 **Your AI Research Assistant is ready for production!**