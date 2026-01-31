# LLM Provider Configuration Guide

SportSQL now supports multiple LLM providers with Gemini as the default and OpenAI GPT as an alternative.

## 🚀 Quick Start

### Using Gemini (Default)

```bash
# No changes needed - works as before
python app.py --server local
python evaluate_pipeline.py
```

### Using OpenAI GPT

```bash
# Add --llm openai to any command
python app.py --server local --llm openai
python evaluate_pipeline.py --llm openai
python test_evaluation.py --llm openai
```

## ⚙️ Environment Variables

### For Gemini (Default)

```bash
# .env file
API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
```

### For OpenAI

```bash
# .env file
OPENAI_API_KEY=your_openai_api_key
GPT_MODEL=gpt-4o-mini  # or gpt-4o
```

### Override Default Provider

```bash
# Force a specific provider globally
LLM_PROVIDER=openai  # or gemini
```

## 🔧 Usage Examples

### Command Line Arguments

```bash
# Use Gemini (default)
python evaluate_pipeline.py

# Use OpenAI GPT
python evaluate_pipeline.py --llm openai
python evaluate_pipeline.py --llm gpt  # same as openai

# Test specific models
python llm_wrapper.py --llm openai --model gpt-4o
python llm_wrapper.py --llm gemini --model gemini-1.5-pro
```

### Programmatic Usage

```python
from llm_wrapper import LLMWrapper, get_global_llm

# Use global instance (respects CLI args)
llm = get_global_llm()
response = llm.generate_content("Your prompt here")

# Create specific provider
llm_gpt = LLMWrapper(provider='openai', model='gpt-4o')
response = llm_gpt.generate_content("Your prompt here")

# Quick generation
from llm_wrapper import generate_with_llm
response = generate_with_llm("Your prompt", provider='openai')
```

## 📊 Provider Comparison

| Feature         | Gemini               | OpenAI GPT       |
| --------------- | -------------------- | ---------------- |
| **Default**     | ✅ Yes               | ❌ No            |
| **Cost**        | 💰 Lower             | 💰💰 Higher      |
| **Rate Limits** | ⚠️ Stricter          | ✅ More generous |
| **SQL Quality** | ✅ Good              | ✅ Excellent     |
| **Reliability** | ⚠️ Occasional issues | ✅ Very reliable |
| **Speed**       | ✅ Fast              | ✅ Fast          |

## 🛠️ Installation

### Install OpenAI Support

```bash
pip install openai>=1.0.0
```

### Or install all dependencies

```bash
pip install -r requirements.txt
```

## 📋 Command Reference

### All SportSQL Scripts Support --llm Flag

#### Main Application

```bash
python app.py --server local --llm openai
```

#### Evaluation Scripts

```bash
python evaluate_pipeline.py --llm openai
python test_evaluation.py --llm openai
```

#### GT SQL Update (if you recreate it)

```bash
python update_gt_sql.py --llm openai
```

#### Direct Testing

```bash
python llm_wrapper.py --llm openai --prompt "Test prompt"
```

## 🔍 Troubleshooting

### Missing API Keys

```bash
# Error: "API key not found"
# Solution: Set the appropriate environment variable
export OPENAI_API_KEY=your_key_here
# or
export API_KEY=your_gemini_key_here
```

### Rate Limiting

```bash
# Gemini rate limits hit
python your_script.py --llm openai  # Switch to OpenAI

# OpenAI rate limits hit
python your_script.py --llm gemini  # Switch to Gemini
```

### Dependencies

```bash
# Missing google-generativeai
pip install google-generativeai

# Missing openai
pip install openai>=1.0.0
```

## 🎯 Best Practices

### 1. **Development**: Use Gemini (cheaper)

```bash
python evaluate_pipeline.py  # Uses Gemini by default
```

### 2. **Production**: Use OpenAI (more reliable)

```bash
LLM_PROVIDER=openai python app.py --server remote
```

### 3. **Batch Processing**: Switch providers if rate limited

```bash
# If Gemini hits limits, switch to OpenAI
python evaluate_pipeline.py --llm openai
```

### 4. **Cost Optimization**: Use smaller models

```bash
# Use cheaper models
export GPT_MODEL=gpt-4o-mini
export GEMINI_MODEL=gemini-1.5-flash
```

## 🔄 Migration Path

The wrapper maintains full backward compatibility:

1. **No changes needed** for existing Gemini usage
2. **Add --llm openai** to switch providers
3. **Set OPENAI_API_KEY** environment variable
4. **All existing scripts work** with both providers

## 🧪 Testing

### Test Both Providers

```bash
# Test Gemini
python llm_wrapper.py --llm gemini --prompt "SELECT COUNT(*) FROM players"

# Test OpenAI
python llm_wrapper.py --llm openai --prompt "SELECT COUNT(*) FROM players"
```

### Test Integration

```bash
# Test with actual SportSQL pipeline
python -c "
import sys
sys.argv.extend(['--server', 'local', '--llm', 'openai'])
from gemini_api import generate_sql
print(generate_sql('How many goals has Haaland scored?'))
"
```

This unified approach gives you the flexibility to choose the best LLM for each task while maintaining full compatibility with existing code! 🚀
