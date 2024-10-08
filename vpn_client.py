import subprocess
import requests
import tempfile
import os
import time
import psutil
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_vpn_servers():
    logger.info("Fetching VPN servers...")
    url = "https://www.vpngate.net/api/iphone/"
    response = requests.get(url)
    servers = []
    for line in response.text.split('\n')[2:]:
        parts = line.split(',')
        if len(parts) > 15:
            servers.append({
                'country': parts[6],
                'ip': parts[1],
                'score': int(parts[2]),
                'ping': int(parts[3]),
                'speed': int(parts[4]),
                'config_data': parts[14]
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
    except subprocess.CalledProcessError:
        logger.error("Failed to connect to VPN. Make sure OpenVPN is installed and you have necessary permissions.")
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
    while True:
        servers = get_vpn_servers()
        if not servers:
            logger.warning("No servers available. Retrying in 60 seconds...")
            time.sleep(60)
            continue

        server = servers.pop(0)
        logger.info(f"Connecting to server in {server['country']} (IP: {server['ip']}, Score: {server['score']})")
        
        vpn_process = subprocess.Popen(['sudo', 'openvpn', '--config', create_config_file(server)])
        
        if monitor_traffic():
            logger.info("Changing server due to unusual traffic...")
            vpn_process.terminate()
            vpn_process.wait()
        else:
            break

def create_config_file(server):
    logger.info(f"Creating temporary config file for server in {server['country']}")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ovpn') as temp_config:
        temp_config.write(server['config_data'])
        return temp_config.name

def main():
    logger.info("Starting VPN client...")
    vpn_manager()

if __name__ == "__main__":
    main()