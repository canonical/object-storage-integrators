# Object-Storage-integrator
[![Charmhub](https://charmhub.io/azure-storage-integrator/badge.svg)](https://charmhub.io/azure-storage-integrator)
[![Release](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml)
[![Tests](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml)

## Description

This is an operator charm providing an integrator for connecting to Azure Storage.


## Instructions for Usage
1. First off all, deploy the `azure-storage-integrator` charm as:
    ```
    juju deploy azure-storage-integrator
    ```

2. Configure the Azure Storage Integrator charm as:
    ```
    juju config azure-storage-integrator storage-account=stoacc container=conn
    ```

3. Add a new secret to Juju, and grant it's permissions to azure-storage-integrator:
    ```
    juju add-secret mysecret secret-key=changeme
    juju grant-secret mysecret azure-storage-integrator
    ```

4. Configure the Azure Storage Integrator charm:
    ```
    juju config azure-storage-integrator credentials=secret-xxxxxxxxxxxxxxxxxxxx
    ```

5. Now the charm should be in active and idle condition. To relate it with a consumer charm, simply do:
    ```
    juju integrate azure-storage-integrator:azure-storage-credentials consumer-charm:some-interface
    ```

Now whenever the user changes the configuration options in azure-storage-integrator charm, appropriate event handlers are fired
so that the charms that consume the relation on the requirer side sees the latest information.


## Security
Security issues in the Charmed Object Storage Integrator Operator can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.


## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/object-storage-integrators/blob/main/CONTRIBUTING.md) for developer guidance.

