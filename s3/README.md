# S3-integrator

[![Charmhub](https://charmhub.io/s3-integrator/badge.svg)](https://charmhub.io/s3-integrator)

<!-- TODO(docs): Add the proper badge both here and in azure-storage -->
<!-- [![Release](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/release.yaml) -->
<!-- [![Tests](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml/badge.svg)](https://github.com/canonical/object-storage-integrators/actions/workflows/ci.yaml) -->

## Description

This is an operator charm providing an integrator for connecting to S3.


> [!WARNING]
> This project is the Juju secrets based S3-integrator charm on track `2/`.
>
> The former action-based `s3-integrator` (on track `1/`) lives in https://github.com/canonical/s3-integrator.

> [!WARNING]
> In-place refresh is not supported for `s3-integrator` from track `1/` to track `2/`,
> because the charms in two channels use different Ubuntu bases.
>

## Instructions for Usage

<!-- TODO(release): figure out the channels -->

1. First off all, deploy the `s3-integrator` charm as:
   ```
   juju deploy s3-integrator --channel=<CHANNEL>
   ```

2. Configure the S3 Integrator charm as:
   ```
   juju config s3-integrator bucket=mybucket
   ```

3. Add a new secret to Juju, and grant its permissions to s3-integrator:
   ```
   juju add-secret mysecret access-key=<ACCESS_KEY> secret-key=<SECRET_KEY>
   juju grant-secret mysecret s3-integrator
   ```
   The first command will return an ID like `secret:d0erdgfmp25c762i8np0`

4. Configure the S3 Integrator charm credentials with the ID above:
   ```
   juju config s3-integrator credentials=secret:d0erdgfmp25c762i8np0
   ```

5. Now the charm should be in active and idle condition. To relate it with a consumer charm, simply do:
   ```
   juju integrate s3-integrator:s3-credentials consumer-charm:some-interface
   ```

Now whenever the user changes the configuration options in s3-integrator charm, appropriate event handlers are fired
so that the charms that consume the relation on the requirer side sees the latest information.

### Further configuration

To configure the S3 integrator charm, you may provide the following configuration options:
  
- `endpoint`: the endpoint used to connect to the object storage.
- `bucket`: the bucket/container name delivered by the provider (the bucket name can be specified also on the requirer application).
- `region`: the region used to connect to the object storage.
- `path`: the path inside the bucket/container to store objects.
- `attributes`: the custom metadata (HTTP headers).
- `s3-uri-style`: the S3 protocol specific bucket path lookup type.
- `storage-class`:the storage class for objects uploaded to the object storage.
- `tls-ca-chain`: the complete CA chain, which can be used for HTTPS validation.
- `s3-api-version`: the S3 protocol specific API signature.
- `experimental-delete-older-than-days`: the amount of day after which backups going to be deleted. EXPERIMENTAL option.


The only mandatory fields for the integrator are access-key secret-key and bucket.

In order to set ca-chain certificate use the following command:
```bash
juju config s3-integrator tls-ca-chain="$(base64 -w0 your_ca_chain.pem)"
```
Attributes needs to be specified in comma-separated format. 


## Security

Security issues in the Charmed Object Storage Integrator Operator can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/object-storage-integrators/blob/main/CONTRIBUTING.md) for developer guidance.
