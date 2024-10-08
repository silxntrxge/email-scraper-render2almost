import subprocess
import tempfile
import os
import time
import logging
import csv
import base64
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_vpn_servers():
    logger.info("Reading VPN servers from local data...")
    servers = []
    with open('textfile.txt', 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)  # Skip the header row
        for row in csv_reader:
            if len(row) > 14 and row[0] != '*':
                try:
                    servers.append({
                        'country': row[6],
                        'ip': row[1],
                        'score': int(row[2]),
                        'ping': int(row[3]),
                        'speed': int(row[4]),
                        'config_data': row[14]
                    })
                except ValueError as e:
                    logger.warning(f"Skipping invalid row: {row}. Error: {e}")
    
    logger.info(f"Found {len(servers)} VPN servers")
    return sorted(servers, key=lambda x: x['score'], reverse=True)

def connect_vpn(server):
    logger.info(f"Attempting to connect to VPN server in {server['country']} (IP: {server['ip']})...")
    config_data = base64.b64decode(server['config_data']).decode('utf-8')
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_config:
        temp_config.write(config_data)
        config_path = temp_config.name

    try:
        # Instead of using OpenVPN directly, we'll use proxychains
        subprocess.run(['proxychains', '-f', config_path, 'curl', 'https://api.ipify.org'], check=True, timeout=30)
        logger.info(f"Successfully connected to VPN server in {server['country']}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to connect to VPN. Error: {e}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Connection attempt timed out")
        return False
    finally:
        os.unlink(config_path)

def monitor_traffic():
    logger.info("Monitoring traffic...")
    try:
        response = requests.get('https://api.ipify.org')
        ip = response.text
        logger.info(f"Current IP: {ip}")
        return False  # No unusual traffic detected
    except Exception as e:
        logger.error(f"Error checking IP: {e}")
        return True  # Assume unusual traffic

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