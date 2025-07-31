from abc import ABC, abstractmethod

class CloudProvider(ABC):
    """
    An abstract base class for cloud service providers.
    This defines a common interface for interacting with different cloud platforms
    (e.g., GCP, AWS) for VM and traffic management.
    """

    @abstractmethod
    def get_vm_egress_traffic_gb(self) -> float:
        """
        Fetches the cumulative egress traffic for the monitored VM for the current
        billing cycle.
        
        Returns:
            float: The total egress traffic in Gigabytes (GB).
        """
        pass

    @abstractmethod
    def shutdown_vm(self):
        """
        Shuts down (stops) the monitored VM instance.
        """
        pass

    @abstractmethod
    def start_vm(self):
        """
        Starts the monitored VM instance.
        """
        pass

    @abstractmethod
    def get_vm_status(self) -> str:
        """
        Gets the current status of the monitored VM instance (e.g., 'RUNNING', 'TERMINATED').

        Returns:
            str: The current status of the VM.
        """
        pass
