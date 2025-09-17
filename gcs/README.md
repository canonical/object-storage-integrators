# GCS-integrator
[![Charmhub](https://charmhub.io/gcs-integrator/badge.svg)](https://charmhub.io/gcs-integrator)
[![Release](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml)

## Description

This is an operator charm providing an integrator for connecting to Google Cloud Storage.


## Instructions for Usage
1. First off all, deploy the `gcs-integrator` charm as:
    ```
    juju deploy gcs-integrator
    ```

2. Configure the GC Storage Integrator charm as:
    ```
    juju config gcs-integrator bucket=foo
    ```

3. Add a new secret to Juju, and grant it's permissions to gcs-integrator using a valid service account JSON file.
    ```
    juju add-secret mysecret secret-key="$(cat service_account.json)"
    juju grant-secret mysecret gcs-integrator
    ```

4. Configure the Google Cloud Storage Integrator charm:
    ```
    juju config gcs-integrator credentials=secret-xxxxxxxxxxxxxxxxxxxx
    ```

5. Now the charm should be in active and idle condition. To relate it with a consumer charm, simply do:
    ```
    juju integrate gcs-integrator:gcs-credentials consumer-charm:some-interface
    ```

Now whenever the user changes the configuration options in gcs-integrator charm, appropriate event handlers are fired
so that the charms that consume the relation on the requirer side sees the latest information.


## Security
Security issues in the Charmed Object Storage Integrator Operator can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.


## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/object-storage-integrators/blob/main/CONTRIBUTING.md) for developer guidance.

