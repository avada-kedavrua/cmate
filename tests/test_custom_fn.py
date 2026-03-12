import os
import socket

import pytest

from cmate.custom_fn import is_port_in_use, path_exists


class TestPathExists:
    """Tests for path_exists function"""

    def test_path_exists_existing_file(self, tmp_path):
        """Test checking existing file"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        assert path_exists(str(test_file)) is True

    def test_path_exists_existing_directory(self, tmp_path):
        """Test checking existing directory"""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        assert path_exists(str(test_dir)) is True

    def test_path_exists_nonexistent(self, tmp_path):
        """Test checking non-existent path"""
        nonexistent = tmp_path / "does_not_exist"
        assert path_exists(str(nonexistent)) is False

    def test_path_exists_relative_path(self, tmp_path, monkeypatch):
        """Test checking relative path"""
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "relative.txt"
        test_file.write_text("content")
        assert path_exists("relative.txt") is True

    def test_path_exists_empty_string(self):
        """Test checking empty string path"""
        assert path_exists("") is False

    def test_path_exists_with_exception(self, tmp_path, monkeypatch):
        """Test path_exists when os.path.exists raises TypeError"""

        def mock_exists(path):
            raise TypeError("Type error")

        monkeypatch.setattr(os.path, "exists", mock_exists)
        assert path_exists(str(tmp_path)) is False


class TestIsPortInUse:
    """Tests for is_port_in_use function"""

    def test_is_port_in_use_tcp_available(self):
        """Test checking available TCP port"""
        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        # Port should be available now
        assert is_port_in_use(port, "127.0.0.1", "tcp") is False

    def test_is_port_in_use_tcp_in_use(self):
        """Test checking TCP port in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            port = server.getsockname()[1]
            server.listen(1)

            # Port should be in use
            assert is_port_in_use(port, "127.0.0.1", "tcp") is True

    def test_is_port_in_use_udp_available(self):
        """Test checking available UDP port"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        # Port should be available
        assert is_port_in_use(port, "127.0.0.1", "udp") is False

    def test_is_port_in_use_udp_in_use(self):
        """Test checking UDP port in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            server.bind(("127.0.0.1", 0))
            port = server.getsockname()[1]

            # Port should be in use
            assert is_port_in_use(port, "127.0.0.1", "udp") is True

    def test_is_port_in_use_default_host(self):
        """Test with default host (localhost)"""
        # Just verify it doesn't raise exception
        result = is_port_in_use(12345)
        assert isinstance(result, bool)

    def test_is_port_in_use_default_protocol(self):
        """Test with default protocol (tcp)"""
        # Just verify it doesn't raise exception
        result = is_port_in_use(12345, "127.0.0.1")
        assert isinstance(result, bool)

    def test_is_port_in_use_invalid_protocol(self):
        """Test with invalid protocol"""
        with pytest.raises(ValueError):
            is_port_in_use(12345, "127.0.0.1", "invalid")

    def test_is_port_in_use_case_insensitive_protocol(self):
        """Test protocol case insensitivity"""
        # Should work with uppercase
        result_tcp = is_port_in_use(12345, "127.0.0.1", "TCP")
        assert isinstance(result_tcp, bool)

        result_udp = is_port_in_use(12345, "127.0.0.1", "UDP")
        assert isinstance(result_udp, bool)

    def test_is_port_in_use_zero_port(self):
        """Test with port 0 (system assigned)"""
        # Port 0 is a special case, system assigns available port
        result = is_port_in_use(0, "127.0.0.1", "tcp")
        assert isinstance(result, bool)

    def test_is_port_in_use_well_known_port(self):
        """Test with well-known port"""
        # Port 22 (SSH) might be in use on some systems
        # Just verify function doesn't raise exception
        result = is_port_in_use(22, "127.0.0.1", "tcp")
        assert isinstance(result, bool)
