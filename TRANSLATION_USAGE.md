# 🌍 Translation Feature Usage Guide

## Prerequisites

1. **Install Dependencies:**
```bash
pip install google-cloud-translate langdetect
```

2. **Set up Google Cloud Translate (Optional but Recommended):**
```bash
# Method 1: Service Account Key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service-account-key.json"

# Method 2: API Key (simpler)
export GOOGLE_CLOUD_API_KEY="your-api-key-here"
```

3. **Required API Keys:**
```bash
export OPENAI_API_KEY="your-openai-key"
export TAVILY_API_KEY="your-tavily-key"
```

## Usage Methods

### 1. Interactive Multi-Language Research

**Start the interactive CLI:**
```bash
python examples/multilang_research_cli.py interactive
```

**What you'll see:**
- Language selection interface
- Auto-detection options
- Translation preferences
- Rich progress display
- Multilingual results

### 2. Command Line Research

**Research with automatic language detection:**
```bash
python examples/multilang_research_cli.py research "Slavoj Žižek filozofija"
```

**Research with specific languages:**
```bash
python examples/multilang_research_cli.py research \
  "Marx - Freud - Lacan - Žižek connection" \
  --source sl \
  --targets "en,de,fr" \
  --queries 5 \
  --depth advanced
```

**Parameters:**
- `--source`: Source language (sl, en, de, etc.) or auto-detect
- `--targets`: Comma-separated target languages for translation
- `--queries`: Number of search queries (default: 5)
- `--depth`: Search depth (basic/advanced)

### 3. Check Language Support

**View all supported languages:**
```bash
python examples/multilang_research_cli.py languages
```

**Check translation capabilities:**
```bash
python check_languages.py
```

### 4. Test Translation System

**Basic translation test:**
```bash
python test_translation.py
```

**Multi-language research test:**
```bash
python test_multilang_research.py
```

## Example Usage Scenarios

### Scenario 1: Slovenian Philosophy Research
```bash
# Research Slovenian philosophers with results in multiple languages
python examples/multilang_research_cli.py research \
  "slovenski filozofi 21. stoletje" \
  --source sl \
  --targets "en,de,it"
```

### Scenario 2: Cross-Cultural Philosophy
```bash
# Research philosophical connections across cultures
python examples/multilang_research_cli.py research \
  "Continental philosophy vs analytic philosophy" \
  --targets "sl,de,fr" \
  --queries 7 \
  --depth advanced
```

### Scenario 3: Historical Philosophy
```bash
# Research with auto-detection and broad translation
python examples/multilang_research_cli.py research \
  "Heidegger Sein und Zeit influence on Slavoj Žižek" \
  --targets "en,sl,de"
```

## Expected Output

When translation is enabled, you'll see:

1. **Language Detection Results:**
   ```
   🌍 Language Information
   Original Language: sl (Slovenian)
   Research Language: en (English)  
   Target Languages: en, sl, de
   Translation Enabled: True
   ```

2. **Research Results in Multiple Languages:**
   ```
   📋 Executive Summary (English)
   [Summary in English]

   📝 Slovenian (sl)
   [Povzetek in ključne ugotovitve v slovenščini]

   📝 German (de) 
   [Zusammenfassung und wichtige Erkenntnisse auf Deutsch]
   ```

3. **Translation Metadata:**
   - Provider used (Google, DeepL, etc.)
   - Confidence scores
   - Processing times
   - Character counts

## Troubleshooting

### No Translation Providers Available
```bash
# Install Google Cloud Translate
pip install google-cloud-translate

# Set up authentication
export GOOGLE_APPLICATION_CREDENTIALS="path/to/key.json"
```

### Language Detection Issues
```bash
# Install language detection library
pip install langdetect
```

### Unicode Errors (Fixed!)
The system now handles Unicode characters properly, including:
- Slovenian: Žižek, Čeferin, Prešeren
- German: Müller, Weiß, Käfer  
- French: Café, naïve, résumé
- Spanish: Niño, piñata, mañana

### Translation Cache
- Cache location: `translation_cache.db`
- Cache TTL: 24 hours
- Automatic cleanup of expired entries
- View cache stats in CLI

## Advanced Features

### Batch Translation
The system automatically optimizes multiple translations using batch APIs when available.

### Provider Fallback
If Google Translate fails, the system automatically tries:
1. Primary provider (Google for global, DeepL for European)
2. Secondary provider  
3. Fallback language detection

### Analytics Integration
All translations are tracked in the database for:
- Usage analytics
- Cost optimization
- Quality assessment
- Performance monitoring

## Your Specific Use Case

For your Slovenian philosophy research:

```bash
# Perfect command for your Marx-Freud-Lacan-Žižek research
python examples/multilang_research_cli.py research \
  "Marx Freud Lacan Žižek connection controversies Slovenia" \
  --source sl \
  --targets "en,sl,de" \
  --queries 6 \
  --depth advanced
```

This will:
1. ✅ Handle Slovenian characters properly (Žižek)
2. 🔍 Research the philosophical connections
3. 🌍 Provide results in English, Slovenian, and German
4. 📊 Track everything in the database
5. ⚡ Cache translations for future use