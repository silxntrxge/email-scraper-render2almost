import subprocess
import requests
import tempfile
import os
import time
import psutil
import threading

def get_vpn_servers():
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
    return sorted(servers, key=lambda x: x['score'], reverse=True)

def connect_vpn(server):
    config_data = server['config_data']
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ovpn') as temp_config:
        temp_config.write(config_data)
        config_path = temp_config.name

    try:
        subprocess.run(['sudo', 'openvpn', '--config', config_path], check=True)
    except subprocess.CalledProcessError:
        print("Failed to connect to VPN. Make sure OpenVPN is installed and you have necessary permissions.")
    finally:
        os.unlink(config_path)

def monitor_traffic(threshold_mbps=10):
    while True:
        net_io = psutil.net_io_counters()
        bytes_sent, bytes_recv = net_io.bytes_sent, net_io.bytes_recv
        time.sleep(1)
        net_io = psutil.net_io_counters()
        bytes_sent_new, bytes_recv_new = net_io.bytes_sent, net_io.bytes_recv
        
        bytes_total = (bytes_sent_new - bytes_sent) + (bytes_recv_new - bytes_recv)
        mbps = bytes_total * 8 / 1000000  # Convert to Mbps
        
        if mbps > threshold_mbps:
            print(f"Unusual traffic detected: {mbps:.2f} Mbps")
            return True
        
        time.sleep(5)  # Check every 5 seconds

def vpn_manager():
    while True:
        servers = get_vpn_servers()
        if not servers:
            print("No servers available. Retrying in 60 seconds...")
            time.sleep(60)
            continue

        server = servers.pop(0)
        print(f"Connecting to server in {server['country']} (IP: {server['ip']}, Score: {server['score']})")
        
        vpn_process = subprocess.Popen(['sudo', 'openvpn', '--config', create_config_file(server)])
        
        if monitor_traffic():
            print("Changing server due to unusual traffic...")
            vpn_process.terminate()
            vpn_process.wait()
        else:
            break

def create_config_file(server):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ovpn') as temp_config:
        temp_config.write(server['config_data'])
        return temp_config.name

def main():
    print("Starting VPN manager...")
    vpn_manager()

if __name__ == "__main__":
    main()