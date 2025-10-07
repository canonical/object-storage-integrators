# GCS-integrator
[![Charmhub](https://charmhub.io/gcs-integrator/badge.svg)](https://charmhub.io/gcs-integrator)
[![Release](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml)

## Description

This is an operator charm providing an integrator for connecting to Google Cloud Storage.

## Supported Architectures

This charm is released for amd64 and arm64.


## Instructions for Usage
1. Deploy the `gcs-integrator` charm:
    ```
    juju deploy gcs-integrator
    ```
   
Juju will automatically pick the correct artifact for your machines' CPU architecture. To force a specific architecture at deploy time:

**ARM64**
```bash
juju deploy gcs-integrator --constraints arch=arm64
````

2. Set the bucket name:
    ```
    juju config gcs-integrator bucket=foo
    ```
3. Create a service account key (service_account.json) via Console:

   1. IAM & Admin -> Service Accounts -> Create service account (e.g. gcs-integrator).

   2. Grant the minimum roles your workload needs:

     - Read/write objects (recommended minimum): roles/storage.objectAdmin

     - Read-only objects: roles/storage.objectViewer

     - Manage buckets (only if needed): roles/storage.admin

   3. Keys -> Add key -> Create new key -> JSON -> download.
    
    The file looks like the one in below:
```json
{
  "type": "service_account",
  "project_id": "my-project-id",
  "private_key_id": "abcdef1234567890abcdef1234567890abcdef12",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEv......\n-----END PRIVATE KEY-----\n",
  "client_email": "gcs-integrator@my-project-id.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/gcs-integrator%40my-project-id.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
 }
```

4. Add the JSON as a Juju secret and grant it to the integrator.
    ```
    juju add-secret mysecret secret-key#file=service_account.json

    juju grant-secret mysecret gcs-integrator
    ```

5. Configure the GCS Integrator charm by providing Juju secret ID:
    ```
    juju config gcs-integrator credentials=secret-xxxxxxxxxxxxxxxxxxxx
    ```

6. Wait until the charm is active and idle. Then, relate your consumer charm to the integrator:
    ```
    juju integrate gcs-integrator:gcs-credentials consumer-charm:gcs-credentials
    ```

Now whenever the user changes the configuration options in gcs-integrator charm, appropriate event handlers are fired
so that the charms that consume the relation on the requirer side see the latest information.


## Security
Security issues in the GCS Integrator Operator can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.


## Contributing

Please see the [Juju SDK docs](https://documentation.ubuntu.com/juju/3.6/) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/object-storage-integrators/blob/main/CONTRIBUTING.md) for developer guidance.

