#!/usr/bin/env python3
"""
Mock wg-manager script for development and testing on Windows
"""
import sys
import json
from datetime import datetime

def mock_add_client(name):
    """Mock adding a client"""
    print(f"Added client: {name}")
    print(f"IP: 10.8.0.{len(name) % 250 + 2}")
    return 0

def mock_list_clients():
    """Mock listing clients"""
    # Return empty list for now
    print("")
    return 0

def mock_remove_client(name):
    """Mock removing a client"""
    print(f"Removed client: {name}")
    return 0

def mock_status():
    """Mock WireGuard status"""
    print("interface: wg0")
    print("  public key: mockPublicKey123")
    print("  private key: (hidden)")
    print("  listening port: 51820")
    print("")
    print("peer: mockPeerKey456")
    print("  endpoint: 127.0.0.1:51820")
    print("  allowed ips: 10.8.0.0/24")
    print("  latest handshake: 1 minute, 23 seconds ago")
    print("  transfer: 1.2 MB received, 3.4 MB sent")
    return 0

def main():
    if len(sys.argv) < 2:
        print("Usage: mock-wg-manager.py [add|list|remove] [client_name]")
        return 1
    
    command = sys.argv[1]
    
    if command == "add" and len(sys.argv) >= 3:
        client_name = sys.argv[2]
        return mock_add_client(client_name)
    elif command == "list":
        return mock_list_clients()
    elif command == "remove" and len(sys.argv) >= 3:
        client_name = sys.argv[2]
        return mock_remove_client(client_name)
    elif command == "status":
        return mock_status()
    else:
        print(f"Unknown command: {command}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
