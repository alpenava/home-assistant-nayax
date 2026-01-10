# Nayax Vending Machines for Home Assistant

A Home Assistant custom integration that monitors Nayax vending machines via the Lynx operational API. Get real-time notifications when sales happen on your vending machines.

## Features

- **Automatic Machine Discovery** — Machines are discovered automatically from your Nayax account
- **Real-time Sale Events** — Fires `nayax_sale` events when successful transactions occur
- **Device Integration** — Each vending machine appears as a device in Home Assistant
- **Configurable Polling** — Adjust how frequently sales are checked (default: 30 seconds)
- **Persistent State** — Survives Home Assistant restarts without duplicate notifications

## Requirements

- Home Assistant 2023.1 or newer
- Nayax Lynx platform access
- Your Nayax **Actor ID** and **API Token**

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alpenava&repository=home-assistant-nayax&category=integration)

Or manually:

1. Open HACS in Home Assistant
2. Click the three dots menu (⋮) → **Custom repositories**
3. Add `https://github.com/alpenava/home-assistant-nayax` as the repository URL
4. Select **Integration** as the category
5. Click **Add**
6. Search for "Nayax" in HACS and click **Download**
7. Restart Home Assistant

> **Note:** Make sure to download from a release version (not a commit) for best compatibility.

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `custom_components/nayax` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

Your directory structure should look like:

```
config/
└── custom_components/
    └── nayax/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── strings.json
        └── translations/
            └── en.json
```

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **Nayax**
4. Enter your credentials:
   - **Actor ID** — Your Nayax Actor ID from the Lynx platform
   - **API Token** — Your Nayax API token
   - **Polling Interval** — How often to check for new sales (10-300 seconds, default: 30)

The integration will automatically discover all vending machines associated with your account and register them as devices.

## Usage

### Events

When a successful sale occurs, the integration fires a `nayax_sale` event with the following data:

| Field | Description | Example |
|-------|-------------|---------|
| `machine_id` | Nayax machine ID | `"955773629"` |
| `machine_name` | Machine friendly name | `"01 Mehrzweckhalle Piding"` |
| `transaction_id` | Unique transaction ID | `"6526108450"` |
| `amount` | Sale amount | `2.00` |
| `currency` | Currency code | `"EUR"` |
| `product_name` | Product sold | `"Haribo Fruchtgummi Pommes Sauer"` |
| `payment_method` | Payment type | `"Credit Card"` |
| `timestamp` | Transaction time (GMT) | `"2026-01-08T14:29:30.347"` |
| `raw` | Full Nayax transaction object | `{...}` |

### Automation Examples

#### Announce Sales via Alexa

```yaml
automation:
  - alias: "Vending Machine Sale Announcement"
    trigger:
      - platform: event
        event_type: nayax_sale
    action:
      - service: notify.alexa_media
        data:
          message: >
            Ka-ching! {{ trigger.event.data.product_name }} sold 
            for {{ trigger.event.data.amount }} {{ trigger.event.data.currency }}
            at {{ trigger.event.data.machine_name }}
```

#### Send Mobile Notification

```yaml
automation:
  - alias: "Vending Sale Notification"
    trigger:
      - platform: event
        event_type: nayax_sale
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "💰 Vending Sale"
          message: >
            {{ trigger.event.data.product_name }} - 
            {{ trigger.event.data.amount }} {{ trigger.event.data.currency }}
          data:
            tag: "nayax-sale-{{ trigger.event.data.transaction_id }}"
```

#### Log Sales to a File

```yaml
automation:
  - alias: "Log Vending Sales"
    trigger:
      - platform: event
        event_type: nayax_sale
    action:
      - service: notify.file_notify
        data:
          message: >
            {{ now().isoformat() }} | 
            {{ trigger.event.data.machine_name }} | 
            {{ trigger.event.data.product_name }} | 
            {{ trigger.event.data.amount }} {{ trigger.event.data.currency }}
```

#### Filter by Specific Machine

```yaml
automation:
  - alias: "Sale at Main Location"
    trigger:
      - platform: event
        event_type: nayax_sale
        event_data:
          machine_id: "955773629"
    action:
      - service: light.turn_on
        target:
          entity_id: light.sale_indicator
        data:
          flash: short
```

## Options

After setup, you can change the polling interval:

1. Go to **Settings → Devices & Services**
2. Find the Nayax integration
3. Click **Configure**
4. Adjust the **Polling Interval**

## Troubleshooting

### No machines discovered

- Verify your Actor ID and API Token are correct
- Check the Home Assistant logs for API errors
- Ensure your Nayax account has machines associated with it

### Events not firing

- Only successful transactions (SettlementValue > 0) trigger events
- Check the polling interval isn't set too high
- Look for errors in the Home Assistant logs

### Enable Debug Logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.nayax: debug
```

## How It Works

1. On startup, the integration calls the Nayax API to discover all machines
2. Every 30 seconds (configurable), it polls each machine's recent sales
3. New successful transactions (SettlementValue > 0) trigger `nayax_sale` events
4. Transaction IDs are tracked to prevent duplicate notifications
5. Machine discovery runs every 5 minutes to detect new machines

## Limitations

- Polling-based only (no real-time webhooks)
- Read-only (cannot initiate payments or configure machines)
- Requires active internet connection to Nayax Lynx API

## License

MIT License — See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

## Disclaimer

This integration is not affiliated with, endorsed by, or connected to Nayax Ltd. Use at your own risk.

