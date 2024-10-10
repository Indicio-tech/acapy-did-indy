# acapy-did-indy

## Overview

This plugin provides the following components:

- A did:indy resolver
- A did:indy registar
- Routes for creating a did:indy

The registrar depends on using a nym that has been previously registered on the connected network. The network must also have auth rules that permit nym owners to update their nym or publish attribs about their nym without endorsement. This is the default auth rules configuration for Indy Networks but their are examples of notable networks that did not keep these rules, namely the Sovrin network.

See the demo for an example scenario where a did:indy DID is created to sign an Open Badges v3 credential.

## Configuration

### indy_namespace

This plugin depends on configuring an Indy Namespace for the connected ledger. The connected ledger is the one ACA-Py is configured to write to through flags like `--genesis-url`.

### ledgers

To resolve DIDs from Indy ledgers, a namespace mapping must be provided. This mapping informs the resolver how to determine a network from a namespace. For example, this config value would tell the resolver that the `indicio:test` namespace has genesis txns available at a given URL (using command line argument syntax described in more detail below):

```sh
aca-py start \
    -it http 0.0.0.0 3000
    # etc etc ...
    --plugin acapy_did_indy
    --plugin-config-value acapy_did_indy.ledgers."indicio:test"=https://...
```

### Providing configuration

To configure the plugin with these parameters, there are three potential paths:

> Note: newlines and comments added for demonstration purposes; this may not work as is depending on where you're using it

#### Command line argument

```sh
aca-py start
    -it http 0.0.0.0 3000
    # etc etc ...
    --plugin acapy_did_indy  # load the plugin itself
    --plugin-config-value acapy_did_indy.indy_namespace=indicio:test
    --plugin-config-value acapy_did_indy.ledgers."indicio:test"=https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis
    --plugin-config-value acapy_did_indy.ledgers."indicio:demo"=https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_demonet_genesis
```

Or, the shorthand:

```sh
aca-py start \
    -it http 0.0.0.0 3000
    # etc etc ...
    --plugin acapy_did_indy  # load the plugin itself
    -o acapy_did_indy.indy_namespace=indicio:test
    -o acapy_did_indy.ledgers."indicio:test"=https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis
    -o acapy_did_indy.ledgers."indicio:demo"=https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_demonet_genesis
```

#### Environment Variable

Ledger namespace mapping cannot be specified by environment variable at this time.

To set the Indy Namespace, the environment variable `INDY_NAMESPACE` may be used; e.g.:

```sh
INDY_NAMESPACE=indicio:test aca-py start
    -it http 0.0.0.0 3000
    # Other args etc etc ...
```

#### Plugin Config file

A separate plugin config file may be used:

```yaml
# my-plugin-config.yaml

acapy-did-indy:
    indy_namespace: indicio:test
    ledgers:
        indicio:test: https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_testnet_genesis
        indicio:demo: https://raw.githubusercontent.com/Indicio-tech/indicio-network/main/genesis_files/pool_transactions_demonet_genesis

# Other plugin configurations etc etc ...
```

And then loaded into ACA-Py on startup:

```sh
aca-py start
    -it http 0.0.0.0 3000
    # Other args etc etc ...
    --plugin acapy_did_indy  # load the plugin itself
    --plugin-config my-plugin-config.yaml
```
