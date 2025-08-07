#!/usr/bin/env python3
"""Basic tests for the WoL Game Server Proxy."""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.config_manager import ConfigManager
from src.wol_sender import WoLSender
from src.minecraft_handler import PacketBuffer


class TestConfigManager(unittest.TestCase):
    """Test configuration management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.json')
        
    def test_default_config_load(self):
        """Test loading default configuration."""
        config_manager = ConfigManager('nonexistent.json')
        config = config_manager.load_config()
        
        # Check required sections exist
        self.assertIn('server', config)
        self.assertIn('timing', config)
        self.assertIn('minecraft', config)
        self.assertIn('satisfactory', config)
        
    def test_config_validation(self):
        """Test configuration validation."""
        config_manager = ConfigManager()
        config = config_manager._get_default_config()
        
        # Should validate successfully
        config_manager._config = config
        config_manager._validate_config()
        
    def test_invalid_ip_validation(self):
        """Test IP address validation."""
        config_manager = ConfigManager()
        
        # Test invalid IP
        self.assertFalse(config_manager._validate_ip_address('invalid.ip'))
        self.assertFalse(config_manager._validate_ip_address('256.256.256.256'))
        
        # Test valid IP  
        self.assertTrue(config_manager._validate_ip_address('192.168.1.100'))
        self.assertTrue(config_manager._validate_ip_address('10.0.0.1'))
        
    def test_mac_address_validation(self):
        """Test MAC address validation."""
        config_manager = ConfigManager()
        
        # Test valid MAC addresses
        self.assertTrue(config_manager._validate_mac_address('00:1B:44:11:3A:B7'))
        self.assertTrue(config_manager._validate_mac_address('AA:BB:CC:DD:EE:FF'))
        self.assertTrue(config_manager._validate_mac_address('aa:bb:cc:dd:ee:ff'))
        
        # Test invalid MAC addresses
        self.assertFalse(config_manager._validate_mac_address('invalid'))
        self.assertFalse(config_manager._validate_mac_address('00:1B:44:11:3A'))
        self.assertFalse(config_manager._validate_mac_address('GG:HH:II:JJ:KK:LL'))


class TestWoLSender(unittest.TestCase):
    """Test Wake-on-LAN functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'server': {
                'target_ip': '192.168.1.100',
                'mac_address': '00:1B:44:11:3A:B7'
            },
            'timing': {
                'wol_retry_interval': 1
            }
        }
        
    def test_mac_parsing(self):
        """Test MAC address parsing."""
        wol = WoLSender(self.config)
        
        # Test different MAC formats
        test_cases = [
            ('00:1B:44:11:3A:B7', b'\\x00\\x1b\\x44\\x11\\x3a\\xb7'),
            ('00-1B-44-11-3A-B7', b'\\x00\\x1b\\x44\\x11\\x3a\\xb7'),
            ('001B44113AB7', b'\\x00\\x1b\\x44\\x11\\x3a\\xb7')
        ]
        
        for mac_str, expected_bytes in test_cases:
            config = self.config.copy()
            config['server']['mac_address'] = mac_str
            wol = WoLSender(config)
            self.assertEqual(wol.mac_bytes, expected_bytes)
    
    def test_magic_packet_creation(self):
        """Test magic packet creation."""
        wol = WoLSender(self.config)
        packet = wol._create_magic_packet()
        
        # Magic packet should be 102 bytes (6 + 16*6)
        self.assertEqual(len(packet), 102)
        
        # First 6 bytes should be 0xFF
        self.assertEqual(packet[:6], b'\\xff' * 6)
        
        # Next 96 bytes should be MAC repeated 16 times
        expected_mac_section = wol.mac_bytes * 16
        self.assertEqual(packet[6:], expected_mac_section)
    
    def test_configuration_validation(self):
        """Test WoL configuration validation."""
        # Valid configuration
        wol = WoLSender(self.config)
        self.assertTrue(wol.validate_configuration())
        
        # Invalid MAC address
        invalid_config = self.config.copy()
        invalid_config['server']['mac_address'] = 'invalid'
        with self.assertRaises(ValueError):
            WoLSender(invalid_config)


class TestMinecraftPacketBuffer(unittest.TestCase):
    """Test Minecraft packet buffer operations."""
    
    def test_varint_operations(self):
        """Test VarInt read/write operations."""
        buffer = PacketBuffer()
        
        # Test various VarInt values
        test_values = [0, 127, 128, 255, 16383, 16384, 2097151]
        
        for value in test_values:
            # Write value
            write_buffer = PacketBuffer()
            write_buffer.write_varint(value)
            
            # Read value back
            read_buffer = PacketBuffer(write_buffer.data)
            read_value = read_buffer.read_varint()
            
            self.assertEqual(value, read_value)
    
    def test_string_operations(self):
        """Test string read/write operations."""
        test_strings = [
            "Hello World",
            "Test with unicode: §a§b§c",
            "",
            "Long string " * 100
        ]
        
        for test_string in test_strings:
            # Write string
            write_buffer = PacketBuffer()
            write_buffer.write_string(test_string)
            
            # Read string back
            read_buffer = PacketBuffer(write_buffer.data)
            read_string = read_buffer.read_string()
            
            self.assertEqual(test_string, read_string)
    
    def test_ushort_operations(self):
        """Test unsigned short read/write operations."""
        test_values = [0, 255, 256, 65535]
        
        for value in test_values:
            # Write value
            write_buffer = PacketBuffer()
            write_buffer.write_ushort(value)
            
            # Read value back
            read_buffer = PacketBuffer(write_buffer.data)
            read_value = read_buffer.read_ushort()
            
            self.assertEqual(value, read_value)


class TestMinecraftProtocol(unittest.TestCase):
    """Test Minecraft protocol handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'minecraft': {
                'port': 25565,
                'protocol_version': 763,
                'motd_offline': '§aJoin to start server',
                'motd_starting': '§eServer is starting',
                'version_text_starting': 'Starting...',
                'kick_message': '§eServer starting',
                'max_players_display': 20
            }
        }
    
    def test_status_response_creation(self):
        """Test status response JSON creation."""
        from src.minecraft_handler import MinecraftHandler
        
        handler = MinecraftHandler(self.config)
        
        # Test offline status
        offline_status = handler.create_status_response(is_starting=False)
        offline_data = json.loads(offline_status)
        
        self.assertEqual(offline_data['description'], '§aJoin to start server')
        self.assertEqual(offline_data['version']['name'], 'WoL Proxy')
        self.assertEqual(offline_data['players']['online'], 0)
        
        # Test starting status
        starting_status = handler.create_status_response(is_starting=True)
        starting_data = json.loads(starting_status)
        
        self.assertEqual(starting_data['description'], '§eServer is starting')
        self.assertEqual(starting_data['version']['name'], 'Starting...')


if __name__ == '__main__':
    unittest.main()