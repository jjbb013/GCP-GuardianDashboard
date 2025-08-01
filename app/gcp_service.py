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
from .config import ServerConfig
from .providers import CloudProvider

class GcpService(CloudProvider):
    """A service to interact with Google Cloud Platform APIs."""

    def __init__(self):
        self._clients_cache = {}  # Cache for API clients, keyed by server.id
        self._instance_id_cache = {}  # Cache for numerical instance IDs, keyed by server.id
        logging.info("GCP Service initialized (clients will be created on-demand).")

    def _get_clients(self, server: ServerConfig) -> dict:
        """
        Creates and caches API clients for a specific server using its SA_KEY.
        Returns a dictionary containing 'compute' and 'monitoring' clients.
        """
        if server.id in self._clients_cache:
            return self._clients_cache[server.id]

        logging.info(f"Creating new API clients for server: {server.id}")
        try:
            creds_json = base64.b64decode(server.sa_key).decode('utf-8')
            creds_info = json.loads(creds_json)
            
            scopes = [
                'https://www.googleapis.com/auth/compute',
                'https://www.googleapis.com/auth/monitoring.read'
            ]
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=scopes
            )
            
            authed_http = AuthorizedHttp(credentials)
            
            compute_client = build('compute', 'v1', http=authed_http)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)

            clients = {
                "compute": compute_client,
                "monitoring": monitoring_client
            }
            self._clients_cache[server.id] = clients
            return clients

        except Exception as e:
            logging.error(f"Failed to create GCP clients for server {server.id}: {e}")
            raise

    def _get_numerical_instance_id(self, server: ServerConfig) -> str:
        """Gets the numerical ID of the VM instance from its name, with caching."""
        if server.id in self._instance_id_cache:
            return self._instance_id_cache[server.id]

        try:
            clients = self._get_clients(server)
            compute = clients['compute']
            logging.info(f"Fetching numerical ID for instance '{server.instance_name}' in project '{server.project_id}'...")
            request = compute.instances().get(
                project=server.project_id,
                zone=server.zone,
                instance=server.instance_name
            )
            response = request.execute()
            numerical_id = response.get('id')
            if not numerical_id:
                raise ValueError(f"Could not retrieve numerical 'id' from instance details for server {server.id}.")
            
            self._instance_id_cache[server.id] = numerical_id
            logging.info(f"Found and cached numerical instance ID: {numerical_id} for server {server.id}")
            return numerical_id
        except Exception as e:
            logging.error(f"Failed to get numerical instance ID for server {server.id}: {e}")
            raise

    def get_vm_egress_traffic_gb(self, server: ServerConfig) -> float:
        """Fetches the cumulative egress traffic for the specified VM for the current month."""
        clients = self._get_clients(server)
        monitoring_client = clients['monitoring']
        
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        project_name = f"projects/{server.project_id}"
        
        numerical_instance_id = self._get_numerical_instance_id(server)

        filter_query = (
            f'metric.type = "compute.googleapis.com/instance/network/sent_bytes_count" '
            f'AND resource.labels.instance_id = "{numerical_instance_id}"'
        )

        interval = monitoring_v3.TimeInterval(
            start_time={"seconds": int(start_of_month.timestamp())},
            end_time={"seconds": int(now.timestamp())},
        )

        alignment_period_seconds = 3600
        aggregation = monitoring_v3.Aggregation(
            alignment_period={"seconds": alignment_period_seconds},
            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
            cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
            group_by_fields=["resource.zone"],
        )

        try:
            logging.info(f"Querying traffic rate for VM '{server.instance_name}' since {start_of_month.isoformat()}Z")
            results = monitoring_client.list_time_series(
                request={
                    "name": project_name,
                    "filter": filter_query,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    "aggregation": aggregation,
                }
            )
            
            total_bytes = sum(point.value.double_value * alignment_period_seconds for series in results for point in series.points)
            traffic_gb = total_bytes / (1024 ** 3)
            logging.info(f"Successfully calculated total traffic for server {server.id}: {traffic_gb:.4f} GB")
            return traffic_gb

        except google.api_core.exceptions.PermissionDenied as e:
            logging.error(f"Permission denied for server {server.id}. Ensure SA has 'Monitoring Viewer' role. Details: {e}")
            raise
        except Exception as e:
            logging.error(f"An error occurred while fetching traffic data for server {server.id}: {e}")
            raise

    def shutdown_vm(self, server: ServerConfig):
        """Shuts down the specified VM instance."""
        clients = self._get_clients(server)
        compute = clients['compute']
        logging.info(f"Attempting to shut down VM '{server.instance_name}' for server {server.id}...")
        try:
            request = compute.instances().stop(project=server.project_id, zone=server.zone, instance=server.instance_name)
            response = request.execute()
            logging.info(f"Successfully initiated shutdown for VM '{server.instance_name}'. Operation: {response['name']}")
            return response
        except Exception as e:
            logging.error(f"Failed to shut down VM '{server.instance_name}': {e}")
            raise

    def start_vm(self, server: ServerConfig):
        """Starts the specified VM instance."""
        clients = self._get_clients(server)
        compute = clients['compute']
        logging.info(f"Attempting to start VM '{server.instance_name}' for server {server.id}...")
        try:
            request = compute.instances().start(project=server.project_id, zone=server.zone, instance=server.instance_name)
            response = request.execute()
            logging.info(f"Successfully initiated startup for VM '{server.instance_name}'. Operation: {response['name']}")
            return response
        except Exception as e:
            logging.error(f"Failed to start VM '{server.instance_name}': {e}")
            raise

    def get_vm_status(self, server: ServerConfig) -> str:
        """Gets the current status of the specified VM instance."""
        clients = self._get_clients(server)
        compute = clients['compute']
        logging.info(f"Fetching status for VM '{server.instance_name}' in project '{server.project_id}'...")
        
        try:
            request = compute.instances().get(project=server.project_id, zone=server.zone, instance=server.instance_name)
            response = request.execute()
            status = response.get('status', 'UNKNOWN')
            logging.info(f"VM '{server.instance_name}' status is {status}.")
            return status
        except Exception as e:
            logging.error(f"Failed to get status for VM '{server.instance_name}': {e}")
            return "UNKNOWN"

# Singleton instance
gcp_service = GcpService()
