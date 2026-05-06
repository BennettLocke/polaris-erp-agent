"""
硬件扩展接口（预留）
支持串口设备、网络设备对接
"""
from abc import ABC, abstractmethod
from typing import Optional
from src.utils import get_logger

logger = get_logger("sjagent.hardware")


class HardwareDevice(ABC):
    """硬件设备基类"""

    @abstractmethod
    def connect(self) -> bool:
        """连接设备"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def send(self, data: bytes) -> bool:
        """发送数据"""
        pass

    @abstractmethod
    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """接收数据"""
        pass


class SerialDevice(HardwareDevice):
    """
    串口设备

    预留用于：打印机、扫描枪、称重设备等
    """

    def __init__(self, port: str = "COM1", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self._serial = None

    def connect(self) -> bool:
        """连接串口设备"""
        try:
            import serial
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
            )
            logger.info(f"串口连接成功: {self.port}, baudrate={self.baudrate}")
            return True
        except Exception as e:
            logger.error(f"串口连接失败: {e}")
            return False

    def disconnect(self):
        """断开串口连接"""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info(f"串口已关闭: {self.port}")

    def send(self, data: bytes) -> bool:
        """发送数据"""
        if not self._serial or not self._serial.is_open:
            return False
        try:
            self._serial.write(data)
            return True
        except Exception as e:
            logger.error(f"串口发送失败: {e}")
            return False

    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """接收数据"""
        if not self._serial or not self._serial.is_open:
            return None
        try:
            self._serial.timeout = timeout
            data = self._serial.read(1024)
            return data if data else None
        except Exception as e:
            logger.error(f"串口接收失败: {e}")
            return None


class NetworkDevice(HardwareDevice):
    """
    网络设备（TCP/UDP）

    预留用于：网络打印机、扫描设备等
    """

    def __init__(self, host: str, port: int, protocol: str = "tcp"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self._socket = None

    def connect(self) -> bool:
        """连接网络设备"""
        try:
            import socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)
            self._socket.connect((self.host, self.port))
            logger.info(f"网络设备连接成功: {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"网络设备连接失败: {e}")
            return False

    def disconnect(self):
        """断开网络连接"""
        if self._socket:
            self._socket.close()
            logger.info(f"网络设备已断开: {self.host}:{self.port}")

    def send(self, data: bytes) -> bool:
        """发送数据"""
        if not self._socket:
            return False
        try:
            self._socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"网络设备发送失败: {e}")
            return False

    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """接收数据"""
        if not self._socket:
            return None
        try:
            self._socket.settimeout(timeout)
            data = self._socket.recv(4096)
            return data if data else None
        except Exception:
            return None


class DeviceManager:
    """
    设备管理器
    统一管理所有硬件设备
    """

    def __init__(self):
        self._devices = {}

    def register(self, name: str, device: HardwareDevice) -> bool:
        """注册设备"""
        try:
            if device.connect():
                self._devices[name] = device
                logger.info(f"设备注册成功: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"设备注册失败: {name}, {e}")
            return False

    def get(self, name: str) -> Optional[HardwareDevice]:
        """获取设备"""
        return self._devices.get(name)

    def unregister(self, name: str):
        """注销设备"""
        device = self._devices.pop(name, None)
        if device:
            device.disconnect()
            logger.info(f"设备已注销: {name}")

    def list_devices(self) -> list[str]:
        """列出所有设备"""
        return list(self._devices.keys())
