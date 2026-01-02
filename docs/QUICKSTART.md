# Quick Start Guide

## For New Users

### Install
```bash
git clone https://github.com/MichaelHamad/wAIting.git
cd wAIting
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Use
```bash
waiting <any-command>
```

### Examples
```bash
waiting python3                          # Bell rings at >>> prompt
waiting npm install                      # Bell rings if input needed
waiting python -c "input('Name: ')"      # Bell rings immediately
```

---

## For Developers (Already Installed)

### Start
```bash
cd /Users/michaelhamad/Documents/GitHub/wAIting
source venv/bin/activate
```

### Test It Works
```bash
waiting python -c "input('test: ')"
# Should hear bell.wav after ~2 seconds
# Bell repeats every 5 seconds until you type
```

### Run Tests
```bash
python -m pytest tests/ -v
```
