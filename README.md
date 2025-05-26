
# Memory Card Backup Tool - Standalone

**A reliable and user-friendly command-line tool for backing up memory cards and removable storage devices.**

This standalone Python script provides cross-platform support, real-time progress indicators, SHA-256 file verification, and detailed backup reporting. All logic is contained in one fileâ€”just install `rich` and run.

---

## Features

- **All-in-One Script**: No external modules or scripts needed
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **Automatic Device Detection**: Identifies removable drives across systems
- **SHA-256 Verification**: Ensures integrity of each copied file
- **Rich CLI Experience**: Uses `rich` for beautiful progress bars and tables
- **Backup Reporting**: Generates `TXT` and `JSON` reports
- **Safe Path Handling**: Prevents directory traversal and illegal characters
- **Interrupt Safe**: Gracefully handles keyboard interruptions

---

## Requirements

- Python 3.7+
- [rich](https://github.com/Textualize/rich) Python library

Install with pip:

```bash
pip install rich
```

---

## Getting Started

### 1. Clone or Download

Download the `memory_card_backup_standalone.py` file or clone the repository.

### 2. Run the Tool

```bash
python memory_card_backup_standalone.py
```

Follow the interactive prompts to:

- Scan and list removable devices
- Select the source device (e.g., SD card or USB)
- Choose a destination folder
- Confirm and start the backup

### Optional: List Devices Only

```bash
python memory_card_backup_standalone.py --list-devices
```

---

## Example

```text
Memory Card Backup Tool
Reliable backup solution for removable storage devices

Scanning for removable storage devices...

Available Devices:
1. SD_CARD (E:\)  â€¢  32 GB  â€¢  exFAT

Select source device (enter number): 1
Enter destination directory: C:\Users\John\Backups

âœ“ Backup completed successfully!
Files copied: 327
Total size: 15.6 GB
Duration: 00:12:41
Report saved: C:\Users\John\Backups\SD_CARD_backup_20250526_113042\backup_report.txt
```

---

## Output

Backups are stored in a subfolder named like:

```
<device>_backup_<YYYYMMDD_HHMMSS>
```

Example:

```
/Backups/SD_CARD_backup_20250526_113042/
```

Each backup folder contains:

- Copied files
- `backup_report.txt` (human-readable)
- `backup_report.json` (machine-readable)

---

## Verification

After copying, the tool automatically verifies each file using SHA-256:

- Compares the original and copied files
- Reports mismatches or failures
- Displays summary in the console

---

## Troubleshooting

- **"No removable devices found"**: Ensure the device is mounted and accessible.
- **Permission errors**: Run with appropriate access or try a different destination.
- **Interrupted backups**: Safe to retry; partial progress is discarded.

---

## Contribution Guide

### How to Contribute

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Commit your changes: `git commit -m "Add your feature"`
5. Push to your fork: `git push origin feature/your-feature`
6. Submit a pull request

### Reporting Issues

Please use GitHub Issues to report bugs or request features. Include:

- A clear and descriptive title
- Steps to reproduce (if applicable)
- System info (OS, Python version, etc.)
- Screenshots or logs if available

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

Built with [rich](https://github.com/Textualize/rich) by Will McGugan for enhanced CLI display.
Tested across Windows 11, macOS Ventura, and Ubuntu 22.04.


# download file
 [**Download memory_card_backup_standalone.py**](./memory_card_backup_standalone%20(copy).py)
