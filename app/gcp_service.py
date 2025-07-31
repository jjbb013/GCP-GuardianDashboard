import base64
import json
import logging
from datetime import datetime, timedelta
import google.api_core.exceptions
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import monitoring_v3
from google_auth_httplib2 import AuthorizedHttp
import httplib2
from .config import settings
from .providers import CloudProvider

class GcpService(CloudProvider):
    """A service to interact with Google Cloud Platform APIs."""

    def __init__(self):
        try:
            # Decode the base64 service account credentials
            creds_json = base64.b64decode(settings.GCP_SERVICE_ACCOUNT_CREDENTIALS).decode('utf-8')
            creds_info = json.loads(creds_json)
            
            # Define the required scopes for the APIs we are using
            scopes = [
                'https://www.googleapis.com/auth/compute',
                'https://www.googleapis.com/auth/monitoring.read'
            ]
            
            self.credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=scopes
            )
            
            # Configure the HTTP proxy
            proxy_info = httplib2.ProxyInfo(
                proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
                proxy_host='127.0.0.1',
                proxy_port=12334
            )
            
            # Create an authorized Http object with the specified proxy
            authed_http = AuthorizedHttp(self.credentials, http=httplib2.Http(proxy_info=proxy_info))
            
            self.compute = build('compute', 'v1', http=authed_http)
            self.monitoring_client = monitoring_v3.MetricServiceClient(credentials=self.credentials)
            self._instance_id = None  # Cache for the numerical instance ID
            logging.info("GCP Service initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize GCP Service: {e}")
            raise

    def _get_numerical_instance_id(self) -> str:
        """Gets the numerical ID of the VM instance from its name."""
        if self._instance_id:
            return self._instance_id

        try:
            logging.info(f"Fetching numerical ID for instance '{settings.GCP_VM_INSTANCE_ID}'...")
            request = self.compute.instances().get(
                project=settings.GCP_PROJECT_ID,
                zone=settings.GCP_VM_ZONE,
                instance=settings.GCP_VM_INSTANCE_ID
            )
            response = request.execute()
            instance_id = response.get('id')
            if not instance_id:
                raise ValueError("Could not retrieve 'id' from instance details.")
            
            self._instance_id = instance_id
            logging.info(f"Found numerical instance ID: {self._instance_id}")
            return self._instance_id
        except Exception as e:
            logging.error(f"Failed to get numerical instance ID: {e}")
            raise

    def get_vm_egress_traffic_gb(self) -> float:
        """
        Fetches the cumulative egress traffic for the specified VM for the current month
        from the GCP Cloud Monitoring API by calculating the rate and summing it up.
        """
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        project_name = f"projects/{settings.GCP_PROJECT_ID}"
        
        # Get the correct numerical instance ID required by the Monitoring API
        numerical_instance_id = self._get_numerical_instance_id()

        filter_query = (
            f'metric.type = "compute.googleapis.com/instance/network/sent_bytes_count" '
            f'AND resource.labels.instance_id = "{numerical_instance_id}"'
        )

        interval = monitoring_v3.TimeInterval(
            start_time={"seconds": int(start_of_month.timestamp())},
            end_time={"seconds": int(now.timestamp())},
        )

        # We align to a rate and then sum the rates over the period.
        # This is more reliable than a single ALIGN_SUM over a long period.
        alignment_period_seconds = 60
        aggregation = monitoring_v3.Aggregation(
            alignment_period={"seconds": alignment_period_seconds},
            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
            cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
            group_by_fields=["resource.zone"],
        )

        try:
            logging.info(f"Querying traffic rate for VM '{settings.GCP_VM_INSTANCE_ID}' since {start_of_month.isoformat()}Z")
            results_iterator = self.monitoring_client.list_time_series(
                request={
                    "name": project_name,
                    "filter": filter_query,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    "aggregation": aggregation,
                }
            )
            
            # Convert iterator to list to avoid consuming it during logging
            results_list = list(results_iterator)
            logging.info(f"Raw API Response from GCP: {results_list}")

            total_bytes = 0
            # The result gives us bytes per second (rate). We need to sum this up.
            # Each point represents the average rate over the alignment_period.
            for series in results_list:
                for point in series.points:
                    # Multiply the rate (bytes/sec) by the period (sec) to get bytes
                    total_bytes += point.value.double_value * alignment_period_seconds
            
            logging.info(f"Calculated total bytes: {total_bytes}")

            traffic_gb = total_bytes / (1024 ** 3)
            logging.info(f"Successfully calculated total traffic: {traffic_gb:.4f} GB from {len(results_list)} series.")
            return traffic_gb

        except google.api_core.exceptions.PermissionDenied as e:
            logging.error(f"Permission denied when querying GCP Monitoring API. Ensure the service account has the 'Monitoring Viewer' role. Details: {e}")
            raise
        except Exception as e:
            logging.error(f"An error occurred while fetching traffic data from GCP: {e}")
            raise

    def shutdown_vm(self):
        """Shuts down the specified VM instance."""
        logging.info(f"Attempting to shut down VM '{settings.GCP_VM_INSTANCE_ID}'...")
        try:
            request = self.compute.instances().stop(
                project=settings.GCP_PROJECT_ID,
                zone=settings.GCP_VM_ZONE,
                instance=settings.GCP_VM_INSTANCE_ID
            )
            response = request.execute()
            logging.info(f"Successfully initiated shutdown for VM '{settings.GCP_VM_INSTANCE_ID}'. Operation: {response['name']}")
            return response
        except Exception as e:
            logging.error(f"Failed to shut down VM '{settings.GCP_VM_INSTANCE_ID}': {e}")
            raise

    def start_vm(self):
        """Starts the specified VM instance."""
        logging.info(f"Attempting to start VM '{settings.GCP_VM_INSTANCE_ID}'...")
        try:
            request = self.compute.instances().start(
                project=settings.GCP_PROJECT_ID,
                zone=settings.GCP_VM_ZONE,
                instance=settings.GCP_VM_INSTANCE_ID
            )
            response = request.execute()
            logging.info(f"Successfully initiated startup for VM '{settings.GCP_VM_INSTANCE_ID}'. Operation: {response['name']}")
            return response
        except Exception as e:
            logging.error(f"Failed to start VM '{settings.GCP_VM_INSTANCE_ID}': {e}")
            raise

    def get_vm_status(self) -> str:
        """Gets the current status of the specified VM instance."""
        logging.info("--- Entering get_vm_status function ---")
        project = settings.GCP_PROJECT_ID
        zone = settings.GCP_VM_ZONE
        instance = settings.GCP_VM_INSTANCE_ID
        
        logging.info(f"--- GCP Settings Loaded ---")
        logging.info(f"Project: '{project}'")
        logging.info(f"Zone: '{zone}'")
        logging.info(f"Instance: '{instance}'")
        logging.info("--------------------------")
        
        logging.info(f"Fetching status for VM '{instance}' in project '{project}', zone '{zone}'...")
        
        if not all([project, zone, instance]):
            logging.error("GCP project, zone, or instance ID is not configured.")
            return "MISCONFIGURED"
            
        try:
            request = self.compute.instances().get(
                project=project,
                zone=zone,
                instance=instance
            )
            response = request.execute()
            status = response.get('status', 'UNKNOWN')
            logging.info(f"VM '{instance}' status is {status}.")
            return status
        except Exception as e:
            logging.error(f"Failed to get status for VM '{instance}': {e}")
            return "UNKNOWN"

# Singleton instance
gcp_service = GcpService()
