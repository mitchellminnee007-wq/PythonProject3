# Foxhole Bot

An automated bot for the game Foxhole (War-Win64-Shipping.exe) written in Python.

## Prerequisites

- **Python 3.7+** - [Download from python.org](https://www.python.org/downloads/)
- **Foxhole Game** - Install and have the game available
- **pip** - Usually comes with Python

## Installation

### 1. Clone or Download the Project

If you haven't already, ensure you have the project files in your working directory.

### 2. Set Up a Virtual Environment (Recommended)

A virtual environment isolates your project dependencies from your system Python.

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.venv\Scripts\activate.bat

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install opencv-python numpy pyautogui requests mss pygetwindow
```

Or install them one by one:

```bash
pip install opencv-python      # Computer vision library
pip install numpy              # Numerical computing
pip install pyautogui          # Control mouse and keyboard
pip install requests           # HTTP library
pip install mss                # Screen capture
pip install pygetwindow        # Get window information
```

## Running the Bot

Before running, ensure:
1. Your virtual environment is activated
2. The Foxhole game is running and visible on your screen
3. The game window is titled "War" (auto-detected)

```bash
python bot.py
```

The bot will automatically detect the Foxhole window position and begin operation.

## Project Structure

```
.
├── bot.py              # Main bot script
├── Templates/          # Game template images for pattern matching
├── Nono/              # Additional resources/modules
├── README.md          # This file
└── .venv/             # Virtual environment (created during setup)
```

## Troubleshooting

### Module Not Found Errors
- Ensure your virtual environment is activated
- Verify all dependencies were installed: `pip list`

### Window Detection Issues
- Make sure the Foxhole game window is not minimized
- The bot will use a default capture region if it cannot find the window

### Permission Denied
- On Windows, you may need to enable PowerShell script execution:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

## Requirements Summary

The bot requires the following Python packages:
- **opencv-python** - Image processing and template matching
- **numpy** - Numerical operations for image processing
- **pyautogui** - Automated mouse and keyboard control
- **requests** - HTTP requests (if needed for external integrations)
- **mss** - Fast multi-threading screen capture
- **pygetwindow** - Window detection and management

## Notes

- The bot includes **PyAutoGUI's FAILSAFE** disabled, so move the mouse to a corner if you need to force-stop it
- Screenshot files are saved for debugging purposes
- Window detection automatically restores minimized windows

## Support

For issues or questions, refer to the code comments in `bot.py` or check the Nono/ directory for additional modules.
