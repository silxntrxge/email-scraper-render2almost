import subprocess
import tempfile
import os
import time
import psutil
import logging
import csv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_vpn_servers():
    logger.info("Reading VPN servers from local data...")
    servers = []
    with open('textfile.txt', 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)  # Skip the header line
        for row in csv_reader:
            if len(row) > 14 and row[0] != '*':  # Ensure we have enough columns and skip the footer
                servers.append({
                    'country': row[6],
                    'ip': row[1],
                    'score': int(row[2]),
                    'ping': int(row[3]),
                    'speed': int(row[4]),
                    'config_data': row[14]
                })
    
    logger.info(f"Found {len(servers)} VPN servers")
    return sorted(servers, key=lambda x: x['score'], reverse=True)

def connect_vpn(server):
    logger.info(f"Attempting to connect to VPN server in {server['country']} (IP: {server['ip']})...")
    config_data = server['config_data']
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ovpn') as temp_config:
        temp_config.write(config_data)
        config_path = temp_config.name

    try:
        subprocess.run(['sudo', 'openvpn', '--config', config_path], check=True)
        logger.info(f"Successfully connected to VPN server in {server['country']}")
        return True
    except subprocess.CalledProcessError:
        logger.error("Failed to connect to VPN. Make sure OpenVPN is installed and you have necessary permissions.")
        return False
    finally:
        os.unlink(config_path)

def monitor_traffic(threshold_mbps=10):
    logger.info("Starting traffic monitoring...")
    while True:
        net_io = psutil.net_io_counters()
        bytes_sent, bytes_recv = net_io.bytes_sent, net_io.bytes_recv
        time.sleep(1)
        net_io = psutil.net_io_counters()
        bytes_sent_new, bytes_recv_new = net_io.bytes_sent, net_io.bytes_recv
        
        bytes_total = (bytes_sent_new - bytes_sent) + (bytes_recv_new - bytes_recv)
        mbps = bytes_total * 8 / 1000000  # Convert to Mbps
        
        if mbps > threshold_mbps:
            logger.warning(f"Unusual traffic detected: {mbps:.2f} Mbps")
            return True
        
        time.sleep(5)  # Check every 5 seconds

def vpn_manager():
    logger.info("Starting VPN manager...")
    servers = get_vpn_servers()
    if not servers:
        logger.error("No VPN servers available. Cannot proceed.")
        return

    for server in servers:
        logger.info(f"Attempting to connect to server in {server['country']} (IP: {server['ip']}, Score: {server['score']})")
        
        if connect_vpn(server):
            if monitor_traffic():
                logger.info("Changing server due to unusual traffic...")
                continue
            else:
                logger.info("VPN connection established and stable.")
                return
        else:
            logger.warning("Failed to connect. Trying next server...")

    logger.error("Failed to establish a stable VPN connection with any server.")

def main():
    logger.info("Starting VPN client...")
    vpn_manager()

if __name__ == "__main__":
    main()