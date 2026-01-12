# Nayax Vending Machines for Home Assistant

A Home Assistant custom integration that monitors Nayax vending machines via the Lynx operational API. Get real-time notifications when sales happen on your vending machines.

## Features

- **Automatic Machine Discovery** — Machines are discovered automatically from your Nayax account
- **Real-time Sale Events** — Fires `nayax_sale` events when successful transactions occur
- **Sensor Entities** — Track last sale amount, product, time, and transaction ID per machine
- **Period Totals** — Sales totals and counts for today, this week, this month, this year, and more
- **Device Integration** — Each vending machine appears as a device in Home Assistant
- **Configurable Polling** — Adjust how frequently sales are checked (default: 30 seconds)
- **Configurable Week Start** — Define your first day of week for weekly totals
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
        ├── sensor.py
        ├── manifest.json
        ├── icon.png
        ├── logo.png
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
   - **First Day of Week** — Which day starts your week for weekly totals (default: Monday)

The integration will automatically discover all vending machines associated with your account and register them as devices.

## Usage

### Sensors

Each vending machine device includes **20 sensor entities**:

#### Last Sale Sensors

| Sensor | Description | Example Value |
|--------|-------------|---------------|
| **Last Sale Amount** | Amount of the last successful sale | `2.00` (EUR) |
| **Last Sale Product** | Product name from last sale | `"Haribo Fruchtgummi"` |
| **Last Sale Time** | Timestamp of last sale | `2026-01-08T14:29:30` |
| **Last Transaction ID** | Transaction reference | `"6526108450"` |

#### Period Total Sensors (Amount)

| Sensor | Description | Resets |
|--------|-------------|--------|
| **Sales Today** | Total sales amount today | Midnight |
| **Sales This Week** | Total sales amount this week | First day of week |
| **Sales This Month** | Total sales amount this month | 1st of month |
| **Sales Last Week** | Total sales amount from previous week | When new week starts |
| **Sales Last Month** | Total sales amount from previous month | When new month starts |
| **Sales Last 6 Months** | Rolling 6-month total | Monthly |
| **Sales This Year** | Total sales amount this year | Jan 1st |
| **Sales Last Year** | Total sales amount from previous year | Jan 1st |

#### Period Total Sensors (Count)

| Sensor | Description |
|--------|-------------|
| **Sales Today Count** | Number of transactions today |
| **Sales This Week Count** | Number of transactions this week |
| **Sales This Month Count** | Number of transactions this month |
| **Sales Last Week Count** | Number of transactions last week |
| **Sales Last Month Count** | Number of transactions last month |
| **Sales Last 6 Months Count** | Number of transactions in last 6 months |
| **Sales This Year Count** | Number of transactions this year |
| **Sales Last Year Count** | Number of transactions last year |

Sensors are named like: `sensor.<machine_name>_last_sale_amount` or `sensor.<machine_name>_sales_today`

These sensors:
- Last sale sensors update every poll cycle (default 30 seconds)
- Period totals accumulate from detected sales (start at 0)
- Have full history in Home Assistant recorder
- Can be used in dashboards, automations, and conditions

> **Note:** Period totals start at 0 and accumulate as sales are detected. Historical data from before the integration was installed is not available.

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
| `site_name` | Site/location name | `"DE"` |
| `raw` | Full Nayax transaction object (optional) | `{...}` |

> **Note:** The `raw` field is included by default but can be disabled in the integration options to reduce event payload size.

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

After setup, you can configure the integration:

1. Go to **Settings → Devices & Services**
2. Find the Nayax integration
3. Click **Configure**
4. Adjust the available options:

| Option | Description | Default |
|--------|-------------|---------|
| **Polling Interval** | How often to check for new sales (10-300 seconds) | 30 |
| **Include raw transaction data** | Include the full Nayax transaction object in events | Enabled |
| **First Day of Week** | Which day starts your week for weekly totals | Monday |

> **Tip:** Disable "Include raw transaction data" if you only need the extracted fields and want smaller event payloads for Node-RED or other automation tools.

> **Tip:** Set "First Day of Week" to Sunday if your business week starts on Sunday (common in the US).

## Troubleshooting

### No machines discovered

- Verify your Actor ID and API Token are correct
- Check the Home Assistant logs for API errors
- Ensure your Nayax account has machines associated with it

### Events not firing

- Only successful transactions (SettlementValue > 0) trigger events
- Check the polling interval isn't set too high
- Look for errors in the Home Assistant logs

### Last sale sensors show "Unknown"

- Last sale sensors only populate after the first successful sale is detected
- Ensure there has been at least one sale with SettlementValue > 0
- Check if the API is returning sales data in the debug logs

### Period totals show 0

- Period totals start at 0 and accumulate from detected sales only
- Historical data from before installation is not fetched from Nayax
- Totals will build up over time as new sales occur

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
4. Last sale sensor entities are updated with transaction details
5. Period totals are incremented (today, week, month, year)
6. Transaction IDs are tracked to prevent duplicate event notifications
7. Machine discovery runs every 5 minutes to detect new machines
8. At midnight/week start/month start/year start, period totals roll over appropriately

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

