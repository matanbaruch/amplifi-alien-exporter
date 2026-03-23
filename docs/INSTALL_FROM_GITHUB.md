# Installing from GitHub Packages

To install the amplifi-alien-exporter package from GitHub Packages, you need to authenticate with GitHub.

## Method 1: Using pip with --index-url (Simple)

```bash
# Create a GitHub Personal Access Token with read:packages scope
# https://github.com/settings/tokens

# Install the package
pip install amplifi-alien-exporter \
  --index-url https://<USERNAME>:<TOKEN>@pypi.pkg.github.com/matanbaruch/simple/
```

## Method 2: Configure pip globally (Recommended)

Create or edit `~/.pip/pip.conf` (Linux/macOS) or `%APPDATA%\pip\pip.ini` (Windows):

```ini
[global]
extra-index-url = https://<USERNAME>:<TOKEN>@pypi.pkg.github.com/matanbaruch/simple/
```

Then install normally:

```bash
pip install amplifi-alien-exporter
```

## Method 3: Using a .netrc file

Create or edit `~/.netrc` (Linux/macOS) or `%HOME%\_netrc` (Windows):

```
machine pypi.pkg.github.com
login <USERNAME>
password <TOKEN>
```

Set permissions:
```bash
chmod 600 ~/.netrc
```

Then install:
```bash
pip install amplifi-alien-exporter \
  --index-url https://pypi.pkg.github.com/matanbaruch/simple/
```

## Creating a Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name like "amplifi-exporter-install"
4. Select the `read:packages` scope
5. Click "Generate token"
6. Copy the token and use it in place of `<TOKEN>` above

**Note**: Store your token securely. Anyone with this token can read packages from your account.

## Verifying Installation

After installation, verify it works:

```bash
amplifi-exporter --help
```

Or run it directly:

```bash
export AMPLIFI_ROUTER_IP=192.168.1.1
export AMPLIFI_PASSWORD=your-router-password
amplifi-exporter
```
