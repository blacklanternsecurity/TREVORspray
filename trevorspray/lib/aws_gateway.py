import logging
import random
import threading
import configparser
from time import sleep
from pathlib import Path
from contextlib import suppress
from urllib.parse import urlparse

log = logging.getLogger("trevorspray.aws_gateway")

AWS_CONFIG_FILE = Path.home() / ".trevorspray" / "aws_config.ini"

# All AWS regions that support API Gateway
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-south-1",
    "sa-east-1",
    "ca-central-1",
]


def load_aws_config():
    """Load AWS credentials from ~/.trevorspray/aws_config.ini"""
    config = configparser.ConfigParser()
    if AWS_CONFIG_FILE.exists():
        config.read(str(AWS_CONFIG_FILE))
        if "aws" in config:
            return dict(config["aws"])
    return {}


def save_aws_config(access_key, secret_key, profile=None):
    """Save AWS credentials to ~/.trevorspray/aws_config.ini"""
    config = configparser.ConfigParser()
    config["aws"] = {}
    if access_key:
        config["aws"]["access_key"] = access_key
    if secret_key:
        config["aws"]["secret_key"] = secret_key
    if profile:
        config["aws"]["profile"] = profile

    AWS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(str(AWS_CONFIG_FILE), "w") as f:
        config.write(f)
    # restrict permissions to owner only
    AWS_CONFIG_FILE.chmod(0o600)
    log.info(f"AWS credentials saved to {AWS_CONFIG_FILE}")


def prompt_aws_credentials():
    """Prompt user for AWS credentials interactively."""
    print()
    log.info("AWS credentials required for API Gateway IP rotation")
    log.info(f"Credentials will be saved to {AWS_CONFIG_FILE} for future use")
    print()

    access_key = input("[USER] AWS Access Key ID: ").strip()
    secret_key = input("[USER] AWS Secret Access Key: ").strip()

    if not access_key or not secret_key:
        return None, None

    # Ask if user wants to save
    save = input("\n[USER] Save credentials to config file for future use? [Y/n]: ").strip().lower()
    if save != "n":
        save_aws_config(access_key, secret_key)

    return access_key, secret_key


class AWSGatewayManager:
    """
    Manages AWS API Gateway instances across multiple regions for IP rotation.
    Each API Gateway acts as an HTTP proxy to the target URL, and each request
    through an API Gateway endpoint gets a different source IP.

    Credentials are resolved in this order:
    1. Explicit --aws-access-key / --aws-secret-key CLI args
    2. --aws-profile CLI arg
    3. Saved config file (~/.trevorspray/aws_config.ini)
    4. Interactive prompt (asks user to enter keys)
    5. boto3 default chain (env vars, ~/.aws/credentials, IAM role)
    """

    def __init__(self, target_url, regions=None, profile=None, access_key=None, secret_key=None):
        self.target_url = target_url
        self.regions = regions or list(AWS_REGIONS)
        self.profile = profile
        self.access_key = access_key
        self.secret_key = secret_key

        # Try loading from config file if no explicit credentials
        if not self.profile and not (self.access_key and self.secret_key):
            saved = load_aws_config()
            if saved.get("access_key") and saved.get("secret_key"):
                log.info(f"Loaded AWS credentials from {AWS_CONFIG_FILE}")
                self.access_key = saved["access_key"]
                self.secret_key = saved["secret_key"]
            elif saved.get("profile"):
                log.info(f"Loaded AWS profile '{saved['profile']}' from {AWS_CONFIG_FILE}")
                self.profile = saved["profile"]

        # If still no credentials, prompt the user
        if not self.profile and not (self.access_key and self.secret_key):
            self.access_key, self.secret_key = prompt_aws_credentials()
            if not self.access_key or not self.secret_key:
                log.warning("No AWS credentials provided, falling back to boto3 default chain")
                self.access_key = None
                self.secret_key = None

        parsed = urlparse(target_url)
        self.target_host = parsed.hostname
        self.target_scheme = parsed.scheme or "https"

        self.gateways = []  # list of {"region": ..., "api_id": ..., "endpoint": ...}
        self.lock = threading.Lock()
        self._started = False

    def _get_client(self, service="apigateway", region=None):
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for AWS IP rotation. Install it with: pip install boto3"
            )

        kwargs = {"service_name": service}
        if region:
            kwargs["region_name"] = region
        if self.profile:
            session = boto3.Session(profile_name=self.profile)
            return session.client(**kwargs)
        elif self.access_key and self.secret_key:
            kwargs["aws_access_key_id"] = self.access_key
            kwargs["aws_secret_access_key"] = self.secret_key
            return boto3.client(**kwargs)
        else:
            return boto3.client(**kwargs)

    def _validate_credentials(self):
        """
        Validate AWS credentials using STS GetCallerIdentity before creating gateways.
        Returns True if credentials are valid, raises RuntimeError otherwise.
        """
        log.info("Validating AWS credentials...")
        try:
            sts = self._get_client(service="sts")
            identity = sts.get_caller_identity()
            account = identity.get("Account", "unknown")
            arn = identity.get("Arn", "unknown")
            log.info(f"AWS credentials valid - Account: {account}, Identity: {arn}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "InvalidClientTokenId" in error_msg or "SignatureDoesNotMatch" in error_msg:
                raise RuntimeError(
                    f"AWS credentials are invalid: {e}\n"
                    "Check your Access Key ID and Secret Access Key.\n"
                    "Use --aws-clear-creds to remove saved credentials."
                )
            elif "ExpiredToken" in error_msg:
                raise RuntimeError(
                    f"AWS credentials have expired: {e}\n"
                    "Please provide new credentials."
                )
            else:
                raise RuntimeError(f"Failed to validate AWS credentials: {e}")

    def start(self):
        """Create API Gateways in all configured regions."""
        if self._started:
            return

        # Validate credentials before doing anything
        self._validate_credentials()

        log.info(f"Creating AWS API Gateways in {len(self.regions)} regions for IP rotation...")
        log.info(f"Target: {self.target_url}")

        threads = []
        for region in self.regions:
            t = threading.Thread(target=self._create_gateway, args=(region,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        if not self.gateways:
            raise RuntimeError(
                "Failed to create any AWS API Gateways. Check your AWS credentials and permissions."
            )

        log.info(f"Successfully created {len(self.gateways)} API Gateway endpoints")
        self._started = True

    def _create_gateway(self, region):
        """Create a single API Gateway in the specified region."""
        try:
            client = self._get_client(region=region)

            # Create REST API
            api = client.create_rest_api(
                name=f"trevorspray-{self.target_host}-{region}",
                description="TREVORspray IP rotation proxy",
                endpointConfiguration={"types": ["REGIONAL"]},
            )
            api_id = api["id"]

            # Get the root resource ID
            resources = client.get_resources(restApiId=api_id)
            root_id = None
            for resource in resources["items"]:
                if resource["path"] == "/":
                    root_id = resource["id"]
                    break

            if not root_id:
                log.error(f"[{region}] Could not find root resource")
                return

            # Create a greedy proxy resource {proxy+}
            proxy_resource = client.create_resource(
                restApiId=api_id,
                parentId=root_id,
                pathPart="{proxy+}",
            )
            proxy_id = proxy_resource["id"]

            # Set up methods and integrations for both root and proxy resources
            for resource_id, path_pattern in [(root_id, "/"), (proxy_id, "/{proxy}")]:
                # Create ANY method
                client.put_method(
                    restApiId=api_id,
                    resourceId=resource_id,
                    httpMethod="ANY",
                    authorizationType="NONE",
                    requestParameters={
                        "method.request.path.proxy": True,
                        "method.request.header.X-My-X-Forwarded-For": True,
                        "method.request.header.X-Forwarded-For": True,
                    } if resource_id == proxy_id else {
                        "method.request.header.X-My-X-Forwarded-For": True,
                        "method.request.header.X-Forwarded-For": True,
                    },
                )

                # Set up HTTP proxy integration
                target_uri = f"{self.target_scheme}://{self.target_host}{path_pattern}"

                integration_params = {
                    "restApiId": api_id,
                    "resourceId": resource_id,
                    "httpMethod": "ANY",
                    "type": "HTTP_PROXY",
                    "integrationHttpMethod": "ANY",
                    "uri": target_uri,
                    "connectionType": "INTERNET",
                    "requestParameters": {
                        "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For",
                    },
                }

                if resource_id == proxy_id:
                    integration_params["requestParameters"]["integration.request.path.proxy"] = "method.request.path.proxy"

                client.put_integration(**integration_params)

            # Deploy API to a stage
            client.create_deployment(
                restApiId=api_id,
                stageName="proxy",
            )

            endpoint = f"https://{api_id}.execute-api.{region}.amazonaws.com/proxy"

            with self.lock:
                self.gateways.append({
                    "region": region,
                    "api_id": api_id,
                    "endpoint": endpoint,
                })

            log.verbose(f"[{region}] Created API Gateway: {endpoint}")

        except Exception as e:
            log.warning(f"[{region}] Failed to create API Gateway: {e}")

    def get_proxy_url(self, original_url):
        """
        Rewrite the original URL to go through a random API Gateway endpoint.
        Returns the rewritten URL using a randomly selected gateway.
        """
        if not self.gateways:
            return original_url

        gateway = random.choice(self.gateways)
        parsed = urlparse(original_url)

        # Reconstruct the path + query
        path = parsed.path or "/"
        if path.startswith("/"):
            path = path[1:]

        proxy_url = f"{gateway['endpoint']}/{path}"
        if parsed.query:
            proxy_url += f"?{parsed.query}"

        return proxy_url

    def stop(self):
        """Delete all created API Gateways."""
        if not self.gateways:
            return

        log.info(f"Cleaning up {len(self.gateways)} AWS API Gateways...")

        threads = []
        for gw in list(self.gateways):
            t = threading.Thread(target=self._delete_gateway, args=(gw,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        self.gateways.clear()
        self._started = False
        log.info("AWS API Gateway cleanup complete")

    def _delete_gateway(self, gateway):
        """Delete a single API Gateway."""
        try:
            client = self._get_client(region=gateway["region"])
            client.delete_rest_api(restApiId=gateway["api_id"])
            log.verbose(f"[{gateway['region']}] Deleted API Gateway {gateway['api_id']}")
        except Exception as e:
            log.warning(
                f"[{gateway['region']}] Failed to delete API Gateway {gateway['api_id']}: {e}"
            )

    def __len__(self):
        return len(self.gateways)

    def __repr__(self):
        return f"AWSGatewayManager({len(self.gateways)} gateways across {len(self.regions)} regions)"
