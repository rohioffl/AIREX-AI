"""
Real diagnostic command sets for cloud-aware investigations.

These are the actual shell commands that run on the target server
via AWS SSM or GCP OS Login SSH. All commands are READ-ONLY.
"""

# ── CPU Diagnostics ──────────────────────────────────────────────
CPU_COMMANDS = [
    "echo '=== SYSTEM INFO ==='",
    "hostname && uname -r",
    "echo ''",
    "echo '=== UPTIME & LOAD ==='",
    "uptime",
    "echo ''",
    "echo '=== CPU INFO ==='",
    "nproc && cat /proc/cpuinfo | grep 'model name' | head -1",
    "echo ''",
    "echo '=== CPU USAGE (vmstat 1 3) ==='",
    "vmstat 1 3 2>/dev/null || echo 'vmstat not available'",
    "echo ''",
    "echo '=== TOP 10 PROCESSES BY CPU ==='",
    "ps aux --sort=-%cpu | head -11",
    "echo ''",
    "echo '=== LOAD AVERAGE HISTORY ==='",
    "cat /proc/loadavg",
    "echo ''",
    "echo '=== RECENT CPU THROTTLING (dmesg) ==='",
    "dmesg -T 2>/dev/null | grep -i -E 'throttl|temperature|thermal' | tail -5 || echo 'No throttling events'",
    "echo ''",
    "echo '=== CGROUP CPU STATS ==='",
    "cat /sys/fs/cgroup/cpu/cpuacct.usage 2>/dev/null || cat /sys/fs/cgroup/cpu.stat 2>/dev/null || echo 'cgroup stats not available'",
]

# ── Memory Diagnostics ───────────────────────────────────────────
MEMORY_COMMANDS = [
    "echo '=== MEMORY OVERVIEW ==='",
    "free -h",
    "echo ''",
    "echo '=== DETAILED MEMORY INFO ==='",
    "cat /proc/meminfo | head -20",
    "echo ''",
    "echo '=== TOP 10 PROCESSES BY MEMORY ==='",
    "ps aux --sort=-%mem | head -11",
    "echo ''",
    "echo '=== OOM KILLER EVENTS (last 24h) ==='",
    "journalctl --since '24 hours ago' 2>/dev/null | grep -i 'oom\\|out of memory' | tail -10 || dmesg -T 2>/dev/null | grep -i 'oom\\|out of memory' | tail -10 || echo 'No OOM events found'",
    "echo ''",
    "echo '=== SWAP USAGE ==='",
    "swapon --show 2>/dev/null || cat /proc/swaps",
    "echo ''",
    "echo '=== MEMORY SLAB TOP 10 ==='",
    "cat /proc/slabinfo 2>/dev/null | sort -k3 -n -r | head -10 || echo 'slabinfo not readable'",
]

# ── Disk Diagnostics ─────────────────────────────────────────────
DISK_COMMANDS = [
    "echo '=== DISK USAGE ==='",
    "df -h",
    "echo ''",
    "echo '=== INODE USAGE ==='",
    "df -i | head -10",
    "echo ''",
    "echo '=== LARGEST FILES (top 15) ==='",
    "find / -xdev -type f -size +100M -exec ls -lh {} \\; 2>/dev/null | sort -k5 -h -r | head -15 || echo 'Find not available or no large files'",
    "echo ''",
    "echo '=== DIRECTORY SIZES (/var, /tmp, /home) ==='",
    "du -sh /var /tmp /home /opt 2>/dev/null | sort -h -r",
    "echo ''",
    "echo '=== DISK I/O STATS ==='",
    "iostat -x 1 2 2>/dev/null | tail -20 || echo 'iostat not available'",
    "echo ''",
    "echo '=== RECENT DISK ERRORS ==='",
    "dmesg -T 2>/dev/null | grep -i -E 'error|fail|i/o' | grep -i -E 'sd|nvme|disk|block' | tail -10 || echo 'No disk errors'",
]

# ── Network Diagnostics ──────────────────────────────────────────
NETWORK_COMMANDS = [
    "echo '=== NETWORK INTERFACES ==='",
    "ip addr show 2>/dev/null || ifconfig",
    "echo ''",
    "echo '=== ROUTING TABLE ==='",
    "ip route show 2>/dev/null || route -n",
    "echo ''",
    "echo '=== DNS RESOLUTION ==='",
    "cat /etc/resolv.conf | grep -v '^#'",
    "nslookup google.com 2>/dev/null | head -5 || echo 'nslookup not available'",
    "echo ''",
    "echo '=== ACTIVE CONNECTIONS ==='",
    "ss -tuln 2>/dev/null | head -20 || netstat -tuln | head -20",
    "echo ''",
    "echo '=== CONNECTION COUNTS BY STATE ==='",
    "ss -s 2>/dev/null || echo 'ss not available'",
    "echo ''",
    "echo '=== RECENT NETWORK ERRORS ==='",
    "dmesg -T 2>/dev/null | grep -i -E 'link|eth|network|dropped' | tail -10 || echo 'No network events'",
    "echo ''",
    "echo '=== IPTABLES DROPS (last 10) ==='",
    "journalctl --since '1 hour ago' 2>/dev/null | grep -i 'drop\\|reject' | tail -10 || echo 'No firewall events'",
]

# ── Service Health ────────────────────────────────────────────────
SERVICE_COMMANDS = [
    "echo '=== SYSTEMD FAILED UNITS ==='",
    "systemctl --failed 2>/dev/null || echo 'systemd not available'",
    "echo ''",
    "echo '=== RECENT SYSTEMD JOURNAL (last 50 lines) ==='",
    "journalctl --no-pager -n 50 --since '30 minutes ago' -p err 2>/dev/null || echo 'journalctl not available'",
    "echo ''",
    "echo '=== DOCKER CONTAINERS (if any) ==='",
    "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null | head -15 || echo 'Docker not available'",
    "echo ''",
    "echo '=== RECENTLY RESTARTED SERVICES ==='",
    "systemctl list-units --type=service --state=activating,deactivating 2>/dev/null || echo 'None'",
]

# ── General Health Check ─────────────────────────────────────────
HEALTH_CHECK_COMMANDS = [
    "echo '=== QUICK HEALTH CHECK ==='",
    "hostname && uname -r",
    "uptime",
    "free -h | head -3",
    "df -h / | tail -1",
    "cat /proc/loadavg",
    "echo ''",
    "echo '=== SYSTEMD STATUS ==='",
    "systemctl --failed --no-legend 2>/dev/null | wc -l | xargs echo 'Failed units:'",
    "echo ''",
    "echo '=== LAST 5 LOGINS ==='",
    "last -5 2>/dev/null || echo 'last command not available'",
]

# ── Map alert types to their diagnostic command sets ─────────────
DIAGNOSTIC_COMMANDS: dict[str, list[str]] = {
    "cpu_high": CPU_COMMANDS,
    "memory_high": MEMORY_COMMANDS,
    "disk_full": DISK_COMMANDS,
    "network_issue": NETWORK_COMMANDS,
    "http_check": NETWORK_COMMANDS + SERVICE_COMMANDS,
    "api_check": NETWORK_COMMANDS + SERVICE_COMMANDS,
    "port_check": NETWORK_COMMANDS,
    "heartbeat_check": HEALTH_CHECK_COMMANDS + SERVICE_COMMANDS,
    "plugin_check": HEALTH_CHECK_COMMANDS + SERVICE_COMMANDS,
    "cron_check": SERVICE_COMMANDS,
    "log_anomaly": SERVICE_COMMANDS,
}


def get_diagnostic_commands(alert_type: str) -> list[str]:
    """Get the appropriate diagnostic commands for an alert type."""
    commands = DIAGNOSTIC_COMMANDS.get(alert_type, HEALTH_CHECK_COMMANDS)
    return commands
