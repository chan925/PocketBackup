#!/usr/bin/env python3
"""
Memory Card Backup Tool - Standalone Version
A reliable command-line tool for backing up memory cards and removable storage devices.

This is a complete standalone version that includes all modules in one file.
Just run: python memory_card_backup_standalone.py

Requirements: pip install rich
"""

import os
import sys
import argparse
import platform
import subprocess
import re
import json
import hashlib
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn,
    FileSizeColumn, TotalFileSizeColumn, TransferSpeedColumn
)

console = Console()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    size_bytes = float(size_bytes)
    i = 0
    
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size_bytes)} {size_names[i]}"
    else:
        return f"{size_bytes:.1f} {size_names[i]}"

def safe_path_join(base_path: Path, relative_path: Union[str, Path]) -> Path:
    """Safely join paths, preventing directory traversal attacks."""
    base_path = Path(base_path).resolve()
    
    if isinstance(relative_path, str):
        relative_path = Path(relative_path)
    
    # Remove any leading slashes or drive letters from relative path
    parts = []
    for part in relative_path.parts:
        if part == '..':
            continue  # Skip parent directory references
        if ':' in part and len(part) == 2:  # Skip drive letters
            continue
        if part.startswith('/') or part.startswith('\\'):
            part = part[1:]
        if part and part != '.':
            parts.append(part)
    
    if not parts:
        return base_path
    
    # Reconstruct the path
    safe_relative = Path(*parts)
    result_path = base_path / safe_relative
    
    # Ensure the result is still within the base directory
    try:
        result_path.resolve().relative_to(base_path.resolve())
        return result_path
    except ValueError:
        raise ValueError(f"Path '{relative_path}' attempts to escape base directory '{base_path}'")

def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing or replacing invalid characters."""
    # Replace invalid characters with underscores
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
    
    # Limit length and strip whitespace
    sanitized = sanitized.strip()[:255]
    
    # Ensure it's not empty or a reserved name
    if not sanitized or sanitized.lower() in ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']:
        sanitized = f"file_{sanitized}"
    
    return sanitized

# =============================================================================
# FILE VERIFIER CLASS
# =============================================================================

class FileVerifier:
    def __init__(self, hash_algorithm: str = 'sha256'):
        self.hash_algorithm = hash_algorithm
        
    def calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> Optional[str]:
        """Calculate hash of a file."""
        try:
            hash_obj = hashlib.new(self.hash_algorithm)
            
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            console.print(f"[red]Error calculating hash for {file_path}: {str(e)}[/red]")
            return None
    
    def verify_files(self, source_file: Path, destination_file: Path) -> Dict:
        """Verify that two files are identical by comparing their hashes."""
        result = {
            'source_file': str(source_file),
            'destination_file': str(destination_file),
            'source_hash': None,
            'destination_hash': None,
            'match': False,
            'error': None,
            'source_size': None,
            'destination_size': None
        }
        
        try:
            # Check if files exist
            if not source_file.exists():
                result['error'] = f"Source file does not exist: {source_file}"
                return result
                
            if not destination_file.exists():
                result['error'] = f"Destination file does not exist: {destination_file}"
                return result
            
            # Check file sizes first (quick check)
            source_size = source_file.stat().st_size
            dest_size = destination_file.stat().st_size
            
            result['source_size'] = source_size
            result['destination_size'] = dest_size
            
            if source_size != dest_size:
                result['error'] = f"File sizes don't match: {source_size} vs {dest_size}"
                return result
            
            # Calculate hashes
            result['source_hash'] = self.calculate_file_hash(source_file)
            result['destination_hash'] = self.calculate_file_hash(destination_file)
            
            if result['source_hash'] is None or result['destination_hash'] is None:
                result['error'] = "Failed to calculate file hashes"
                return result
            
            # Compare hashes
            result['match'] = result['source_hash'] == result['destination_hash']
            
            if not result['match']:
                result['error'] = "File hashes don't match"
            
        except Exception as e:
            result['error'] = str(e)
        
        return result

# =============================================================================
# DEVICE DETECTOR CLASS
# =============================================================================

class DeviceDetector:
    def __init__(self):
        self.system = platform.system().lower()

    def get_removable_devices(self) -> List[Dict[str, str]]:
        """Get list of removable storage devices based on the operating system."""
        try:
            if self.system == "windows":
                return self._get_windows_devices()
            elif self.system == "darwin":  # macOS
                return self._get_macos_devices()
            elif self.system == "linux":
                return self._get_linux_devices()
            else:
                console.print(f"[yellow]Warning: Unsupported operating system: {self.system}[/yellow]")
                return []
        except Exception as e:
            console.print(f"[red]Error detecting devices: {str(e)}[/red]")
            return []

    def _get_windows_devices(self) -> List[Dict[str, str]]:
        """Get removable devices on Windows using WMI."""
        devices = []
        
        try:
            # Use wmic to get removable drives
            cmd = ['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 
                   'size,freespace,caption,volumename,filesystem', '/format:csv']
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) >= 6:
                            caption = parts[1].strip()
                            filesystem = parts[2].strip() or "Unknown"
                            freespace = parts[3].strip()
                            size = parts[5].strip()
                            volumename = parts[6].strip() or f"Drive {caption}"
                            
                            if caption and size and size != "0":
                                devices.append({
                                    'name': volumename,
                                    'mount_point': caption,
                                    'size': self._format_size(int(size)) if size.isdigit() else "Unknown",
                                    'filesystem': filesystem
                                })
            
            # Fallback: Check common drive letters for removable media
            if not devices:
                for drive_letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                    drive_path = f"{drive_letter}:\\"
                    if os.path.exists(drive_path):
                        try:
                            # Check if it's a removable drive
                            cmd = ['wmic', 'logicaldisk', 'where', f'caption="{drive_letter}:"', 
                                   'get', 'drivetype', '/format:value']
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                            
                            if "DriveType=2" in result.stdout:  # Removable drive
                                total, used, free = self._get_disk_usage(drive_path)
                                devices.append({
                                    'name': f"Removable Drive ({drive_letter}:)",
                                    'mount_point': drive_path,
                                    'size': self._format_size(total),
                                    'filesystem': "Unknown"
                                })
                        except:
                            continue
                            
        except subprocess.TimeoutExpired:
            console.print("[yellow]Warning: Device detection timed out[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not detect Windows devices: {str(e)}[/yellow]")
        
        return devices

    def _get_macos_devices(self) -> List[Dict[str, str]]:
        """Get removable devices on macOS."""
        devices = []
        
        try:
            # Parse volumes directory for mounted external drives
            volumes_path = Path('/Volumes')
            if volumes_path.exists():
                for volume in volumes_path.iterdir():
                    if volume.is_dir() and volume.name != "Macintosh HD":
                        try:
                            # Check if it's a removable device by checking mount options
                            mount_result = subprocess.run(['mount'], capture_output=True, text=True)
                            if f"/Volumes/{volume.name}" in mount_result.stdout:
                                # Get filesystem info
                                df_result = subprocess.run(['df', '-h', str(volume)], 
                                                         capture_output=True, text=True)
                                
                                if df_result.returncode == 0:
                                    lines = df_result.stdout.strip().split('\n')
                                    if len(lines) > 1:
                                        parts = lines[1].split()
                                        if len(parts) >= 2:
                                            size = parts[1]
                                            filesystem = "Unknown"
                                            
                                            # Try to get filesystem type
                                            fs_result = subprocess.run(['diskutil', 'info', str(volume)], 
                                                                     capture_output=True, text=True)
                                            if fs_result.returncode == 0:
                                                for line in fs_result.stdout.split('\n'):
                                                    if 'File System Personality:' in line:
                                                        filesystem = line.split(':')[1].strip()
                                                        break
                                            
                                            devices.append({
                                                'name': volume.name,
                                                'mount_point': str(volume),
                                                'size': size,
                                                'filesystem': filesystem
                                            })
                        except:
                            continue
                                
        except Exception as e:
            console.print(f"[yellow]Warning: Could not detect macOS devices: {str(e)}[/yellow]")
        
        return devices

    def _get_linux_devices(self) -> List[Dict[str, str]]:
        """Get removable devices on Linux."""
        devices = []
        
        try:
            # Method 1: Use lsblk to find removable devices
            result = subprocess.run(['lsblk', '-o', 'NAME,SIZE,FSTYPE,MOUNTPOINT,RM', '-J'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    for device in data.get('blockdevices', []):
                        if device.get('rm') == True:  # Removable device
                            self._parse_linux_device(device, devices)
                except json.JSONDecodeError:
                    pass
            
            # Method 2: Fallback - check /media and /mnt directories
            if not devices:
                media_paths = [Path('/media'), Path('/mnt')]
                
                for media_path in media_paths:
                    if media_path.exists():
                        for user_dir in media_path.iterdir():
                            if user_dir.is_dir():
                                for mount_point in user_dir.iterdir():
                                    if mount_point.is_dir():
                                        self._check_linux_mount_point(mount_point, devices)
                    
        except Exception as e:
            console.print(f"[yellow]Warning: Could not detect Linux devices: {str(e)}[/yellow]")
        
        return devices

    def _parse_linux_device(self, device, devices):
        """Parse a Linux device from lsblk output."""
        if device.get('mountpoint'):
            mount_point = device['mountpoint']
            name = device.get('name', 'Unknown')
            size = device.get('size', 'Unknown')
            fstype = device.get('fstype', 'Unknown')
            
            devices.append({
                'name': name,
                'mount_point': mount_point,
                'size': size,
                'filesystem': fstype
            })
        
        # Check children (partitions)
        for child in device.get('children', []):
            self._parse_linux_device(child, devices)

    def _check_linux_mount_point(self, mount_point, devices):
        """Check if a Linux mount point is a valid removable device."""
        try:
            if mount_point.is_dir():
                total, used, free = self._get_disk_usage(str(mount_point))
                if total > 0:
                    devices.append({
                        'name': mount_point.name,
                        'mount_point': str(mount_point),
                        'size': self._format_size(total),
                        'filesystem': "Unknown"
                    })
        except:
            pass

    def _get_disk_usage(self, path: str) -> tuple:
        """Get disk usage statistics for a given path."""
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            return total, used, free
        except:
            # Fallback for Windows
            try:
                import shutil
                total, used, free = shutil.disk_usage(path)
                return total, used, free
            except:
                return 0, 0, 0

    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        return format_size(size_bytes)

# =============================================================================
# BACKUP ENGINE CLASS
# =============================================================================

class BackupEngine:
    def __init__(self):
        self.verifier = FileVerifier()
        self.cancelled = False
        
    def backup(self, source_path: Path, destination_path: Path) -> Dict:
        """Perform backup from source to destination with progress tracking."""
        self.cancelled = False
        start_time = datetime.now()
        
        result = {
            'success': False,
            'source_path': str(source_path),
            'destination_path': str(destination_path),
            'start_time': start_time,
            'end_time': None,
            'duration': None,
            'duration_formatted': None,
            'files_copied': 0,
            'files_failed': 0,
            'total_size': 0,
            'total_size_formatted': None,
            'files_processed': [],
            'failed_files': [],
            'verification_results': {},
            'error': None
        }
        
        try:
            # Validate source path
            if not source_path.exists():
                raise ValueError(f"Source path does not exist: {source_path}")
            
            if not source_path.is_dir():
                raise ValueError(f"Source path is not a directory: {source_path}")
            
            # Create destination directory
            destination_path.mkdir(parents=True, exist_ok=True)
            
            # Scan source directory
            console.print("[yellow]Scanning source directory...[/yellow]")
            file_list = self._scan_directory(source_path)
            
            if not file_list:
                console.print("[yellow]No files found to backup.[/yellow]")
                result['success'] = True
                return result
            
            total_files = len(file_list)
            total_size = sum(f['size'] for f in file_list)
            
            console.print(f"[green]Found {total_files} files ({format_size(total_size)}) to backup[/green]")
            
            # Create progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                "•",
                FileSizeColumn(),
                "•",
                TotalFileSizeColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeElapsedColumn(),
                console=console,
                refresh_per_second=10
            ) as progress:
                
                # Main backup task
                main_task = progress.add_task(
                    "[cyan]Copying files...", 
                    total=total_size
                )
                
                # Copy files
                copied_size = 0
                for file_info in file_list:
                    if self.cancelled:
                        break
                    
                    try:
                        # Copy file
                        file_result = self._copy_file(
                            file_info, 
                            source_path, 
                            destination_path,
                            progress,
                            main_task
                        )
                        
                        if file_result['success']:
                            result['files_copied'] += 1
                            result['files_processed'].append(file_result)
                            copied_size += file_info['size']
                        else:
                            result['files_failed'] += 1
                            result['failed_files'].append(file_result)
                        
                        # Update progress
                        progress.update(main_task, advance=file_info['size'])
                        
                    except KeyboardInterrupt:
                        self.cancelled = True
                        break
                    except Exception as e:
                        error_result = {
                            'source_file': file_info['path'],
                            'destination_file': None,
                            'success': False,
                            'error': str(e),
                            'size': file_info['size']
                        }
                        result['files_failed'] += 1
                        result['failed_files'].append(error_result)
                        progress.update(main_task, advance=file_info['size'])
            
            if self.cancelled:
                result['error'] = "Backup cancelled by user"
                return result
            
            # Verification phase
            if result['files_copied'] > 0:
                console.print("\n[yellow]Verifying backup integrity...[/yellow]")
                verification_results = self._verify_backup(
                    result['files_processed'], 
                    source_path, 
                    destination_path
                )
                result['verification_results'] = verification_results
                
                # Check verification results
                failed_verifications = sum(1 for v in verification_results.values() if not v['match'])
                if failed_verifications > 0:
                    console.print(f"[red]Warning: {failed_verifications} files failed verification![/red]")
            
            # Calculate final statistics
            end_time = datetime.now()
            result['end_time'] = end_time
            result['duration'] = end_time - start_time
            result['duration_formatted'] = str(result['duration']).split('.')[0]
            result['total_size'] = copied_size
            result['total_size_formatted'] = format_size(copied_size)
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            console.print(f"[red]Backup failed: {str(e)}[/red]")
        
        return result
    
    def _scan_directory(self, path: Path) -> List[Dict]:
        """Scan directory and return list of files with metadata."""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(path):
                root_path = Path(root)
                
                for filename in filenames:
                    file_path = root_path / filename
                    
                    try:
                        stat = file_path.stat()
                        relative_path = file_path.relative_to(path)
                        
                        files.append({
                            'path': str(relative_path),
                            'full_path': file_path,
                            'size': stat.st_size,
                            'modified': stat.st_mtime,
                            'is_dir': False
                        })
                    except (OSError, ValueError) as e:
                        console.print(f"[yellow]Warning: Could not access {file_path}: {str(e)}[/yellow]")
                        continue
                        
        except Exception as e:
            console.print(f"[red]Error scanning directory: {str(e)}[/red]")
            
        return files
    
    def _copy_file(self, file_info: Dict, source_root: Path, dest_root: Path, 
                   progress: Progress, task_id) -> Dict:
        """Copy a single file with error handling."""
        source_file = source_root / file_info['path']
        dest_file = safe_path_join(dest_root, file_info['path'])
        
        result = {
            'source_file': str(source_file),
            'destination_file': str(dest_file),
            'success': False,
            'error': None,
            'size': file_info['size']
        }
        
        try:
            # Create destination directory if needed
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_file, dest_file)
            
            # Verify file was copied correctly
            if dest_file.exists() and dest_file.stat().st_size == file_info['size']:
                result['success'] = True
            else:
                result['error'] = "File size mismatch after copy"
                
        except Exception as e:
            result['error'] = str(e)
            
        return result
    
    def _verify_backup(self, processed_files: List[Dict], source_root: Path, 
                      dest_root: Path) -> Dict:
        """Verify backup integrity using file hashes."""
        verification_results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            verify_task = progress.add_task(
                "[green]Verifying files...", 
                total=len(processed_files)
            )
            
            for file_result in processed_files:
                if not file_result['success']:
                    continue
                    
                source_file = Path(file_result['source_file'])
                dest_file = Path(file_result['destination_file'])
                
                if source_file.exists() and dest_file.exists():
                    verification = self.verifier.verify_files(source_file, dest_file)
                    verification_results[file_result['source_file']] = verification
                
                progress.advance(verify_task)
        
        return verification_results

# =============================================================================
# REPORT GENERATOR CLASS
# =============================================================================

class ReportGenerator:
    def generate_report(self, backup_result: Dict, backup_path: Path) -> Path:
        """Generate a comprehensive backup report."""
        # Generate text report
        text_report_path = backup_path / "backup_report.txt"
        self._generate_text_report(backup_result, text_report_path)
        
        # Generate JSON report for programmatic access
        json_report_path = backup_path / "backup_report.json"
        self._generate_json_report(backup_result, json_report_path)
        
        # Display summary in console
        self._display_console_summary(backup_result)
        
        return text_report_path
    
    def _generate_text_report(self, backup_result: Dict, report_path: Path):
        """Generate a human-readable text report."""
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                # Header
                f.write("="*80 + "\n")
                f.write("MEMORY CARD BACKUP REPORT\n")
                f.write("="*80 + "\n\n")
                
                # Backup Information
                f.write("BACKUP INFORMATION\n")
                f.write("-"*50 + "\n")
                f.write(f"Source Path: {backup_result.get('source_path')}\n")
                f.write(f"Destination Path: {backup_result.get('destination_path')}\n")
                f.write(f"Start Time: {backup_result.get('start_time')}\n")
                f.write(f"End Time: {backup_result.get('end_time')}\n")
                f.write(f"Duration: {backup_result.get('duration_formatted')}\n")
                f.write(f"Status: {'SUCCESS' if backup_result.get('success') else 'FAILED'}\n")
                
                if backup_result.get('error'):
                    f.write(f"Error: {backup_result['error']}\n")
                
                f.write("\n")
                
                # Statistics
                f.write("BACKUP STATISTICS\n")
                f.write("-"*50 + "\n")
                f.write(f"Files Successfully Copied: {backup_result.get('files_copied', 0)}\n")
                f.write(f"Files Failed: {backup_result.get('files_failed', 0)}\n")
                f.write(f"Total Data Copied: {backup_result.get('total_size_formatted', '0 B')}\n")
                f.write("\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("Report generated on: " + str(datetime.now()) + "\n")
                
        except Exception as e:
            console.print(f"[red]Error generating text report: {str(e)}[/red]")
    
    def _generate_json_report(self, backup_result: Dict, report_path: Path):
        """Generate a JSON report for programmatic access."""
        try:
            # Convert datetime objects to strings for JSON serialization
            json_data = {}
            for key, value in backup_result.items():
                if isinstance(value, datetime):
                    json_data[key] = value.isoformat()
                else:
                    json_data[key] = value
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, default=str)
                
        except Exception as e:
            console.print(f"[red]Error generating JSON report: {str(e)}[/red]")
    
    def _display_console_summary(self, backup_result: Dict):
        """Display a summary of the backup report in the console."""
        # Create summary table
        table = Table(title="Backup Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        
        table.add_row("Status", "✓ SUCCESS" if backup_result.get('success') else "✗ FAILED")
        table.add_row("Duration", backup_result.get('duration_formatted') or "N/A")
        table.add_row("Files Copied", str(backup_result.get('files_copied', 0)))
        table.add_row("Files Failed", str(backup_result.get('files_failed', 0)))
        table.add_row("Total Size", backup_result.get('total_size_formatted', '0 B'))
        
        verification = backup_result.get('verification_results', {})
        if verification:
            verified_count = len(verification)
            passed_count = sum(1 for v in verification.values() if v.get('match', False))
            failed_count = verified_count - passed_count
            
            table.add_row("Files Verified", str(verified_count))
            table.add_row("Verification Passed", str(passed_count))
            if failed_count > 0:
                table.add_row("Verification Failed", str(failed_count))
        
        console.print("\n")
        console.print(table)
        
        # Show errors if any
        if backup_result.get('error'):
            console.print(Panel(
                f"[red]Error: {backup_result['error']}[/red]",
                title="Backup Error",
                border_style="red"
            ))

# =============================================================================
# MAIN BACKUP TOOL CLASS
# =============================================================================

class MemoryCardBackupTool:
    def __init__(self):
        self.device_detector = DeviceDetector()
        self.backup_engine = BackupEngine()
        self.report_generator = ReportGenerator()

    def display_banner(self):
        """Display the application banner."""
        banner = Text("Memory Card Backup Tool", style="bold blue")
        subtitle = Text("Reliable backup solution for removable storage devices", style="dim")
        
        console.print(Panel.fit(
            f"{banner}\n{subtitle}",
            border_style="blue"
        ))
        console.print()

    def list_devices(self):
        """List all available removable storage devices."""
        console.print("[bold yellow]Scanning for removable storage devices...[/bold yellow]")
        
        devices = self.device_detector.get_removable_devices()
        
        if not devices:
            console.print("[red]No removable storage devices found.[/red]")
            return []

        table = Table(title="Available Devices")
        table.add_column("Index", style="cyan", no_wrap=True)
        table.add_column("Device", style="green")
        table.add_column("Mount Point", style="yellow")
        table.add_column("Size", style="blue")
        table.add_column("File System", style="magenta")

        for i, device in enumerate(devices):
            table.add_row(
                str(i + 1),
                device['name'],
                device['mount_point'],
                device['size'],
                device['filesystem']
            )

        console.print(table)
        return devices

    def select_source_device(self, devices):
        """Allow user to select source device for backup."""
        if not devices:
            return None

        while True:
            try:
                choice = Prompt.ask(
                    "\n[bold]Select source device (enter number)[/bold]",
                    default="1"
                )
                
                index = int(choice) - 1
                if 0 <= index < len(devices):
                    selected_device = devices[index]
                    console.print(f"\n[green]Selected:[/green] {selected_device['name']} at {selected_device['mount_point']}")
                    return selected_device
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                return None

    def select_destination(self):
        """Allow user to select destination directory for backup."""
        while True:
            try:
                default_dest = str(Path.home() / "Backups")
                destination = Prompt.ask(
                    f"\n[bold]Enter destination directory[/bold]",
                    default=default_dest
                )
                
                dest_path = Path(destination)
                
                # Create destination directory if it doesn't exist
                if not dest_path.exists():
                    if Confirm.ask(f"Directory '{dest_path}' doesn't exist. Create it?"):
                        dest_path.mkdir(parents=True, exist_ok=True)
                        console.print(f"[green]Created directory: {dest_path}[/green]")
                    else:
                        continue
                
                if not dest_path.is_dir():
                    console.print("[red]Invalid destination. Please provide a directory path.[/red]")
                    continue
                
                return dest_path
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
                return None
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")

    def create_backup_folder(self, destination, device_name):
        """Create a timestamped backup folder."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_device_name = sanitize_filename(device_name)
        
        backup_folder_name = f"{safe_device_name}_backup_{timestamp}"
        backup_path = destination / backup_folder_name
        
        backup_path.mkdir(exist_ok=True)
        return backup_path

    def run_backup(self, source_path, backup_path):
        """Execute the backup process."""
        console.print(f"\n[bold green]Starting backup...[/bold green]")
        console.print(f"[dim]Source:[/dim] {source_path}")
        console.print(f"[dim]Destination:[/dim] {backup_path}")
        
        if not Confirm.ask("\nProceed with backup?"):
            console.print("[yellow]Backup cancelled by user.[/yellow]")
            return None
        
        try:
            # Start backup process
            result = self.backup_engine.backup(source_path, backup_path)
            
            if result['success']:
                console.print(f"\n[bold green]✓ Backup completed successfully![/bold green]")
                console.print(f"Files copied: {result['files_copied']}")
                console.print(f"Total size: {result['total_size_formatted']}")
                console.print(f"Duration: {result['duration_formatted']}")
                
                # Generate report
                report_path = self.report_generator.generate_report(result, backup_path)
                console.print(f"Report saved: {report_path}")
                
                return result
            else:
                console.print(f"\n[bold red]✗ Backup failed: {result['error']}[/bold red]")
                return None
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Backup interrupted by user.[/yellow]")
            return None
        except Exception as e:
            console.print(f"\n[bold red]✗ Backup failed: {str(e)}[/bold red]")
            return None

    def main(self):
        """Main application entry point."""
        self.display_banner()
        
        try:
            # List available devices
            devices = self.list_devices()
            if not devices:
                sys.exit(1)
            
            # Select source device
            source_device = self.select_source_device(devices)
            if not source_device:
                sys.exit(1)
            
            # Select destination
            destination = self.select_destination()
            if not destination:
                sys.exit(1)
            
            # Create backup folder
            backup_path = self.create_backup_folder(destination, source_device['name'])
            
            # Run backup
            result = self.run_backup(Path(source_device['mount_point']), backup_path)
            
            if result:
                console.print(f"\n[bold blue]Backup saved to: {backup_path}[/bold blue]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Application terminated by user.[/yellow]")
            sys.exit(0)
        except Exception as e:
            console.print(f"\n[bold red]Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Memory Card Backup Tool")
    parser.add_argument("--version", action="version", version="1.0.0")
    parser.add_argument("--list-devices", action="store_true", help="List available devices and exit")
    
    args = parser.parse_args()
    
    tool = MemoryCardBackupTool()
    
    if args.list_devices:
        tool.display_banner()
        tool.list_devices()
        return
    
    tool.main()

if __name__ == "__main__":
    main()