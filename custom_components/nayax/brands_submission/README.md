# Brand Assets for hacs/brands Repository

These files are ready to submit to the [hacs/brands repository](https://github.com/hacs/brands) to get the Nayax logo showing in Home Assistant's Settings → Devices & Services page.

## Files Included

- `icon.png` - 270x270 integration icon
- `logo.png` - 270x270 logo for config flow

## How to Submit

1. **Fork the repository**
   ```
   https://github.com/hacs/brands
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/brands.git
   cd brands
   ```

3. **Create the integration folder**
   ```bash
   mkdir -p custom_integrations/nayax
   ```

4. **Copy these files**
   ```bash
   cp /path/to/icon.png custom_integrations/nayax/
   cp /path/to/logo.png custom_integrations/nayax/
   ```

5. **Commit and push**
   ```bash
   git add custom_integrations/nayax/
   git commit -m "Add Nayax Vending Machines integration branding"
   git push origin main
   ```

6. **Create Pull Request**
   - Go to your fork on GitHub
   - Click "Compare & pull request"
   - Title: `Add Nayax Vending Machines integration`
   - Description: `Adding brand assets for the Nayax Vending Machines custom integration (https://github.com/alpenava/home-assistant-nayax)`

## After Merge

Once the PR is merged:
- Users will see the Nayax logo in Settings → Devices & Services
- No changes needed to the integration itself
- Works automatically for all users with HACS installed

## Image Requirements

The hacs/brands repository prefers:
- `icon.png` - Square, 256x256 or larger (we have 270x270 ✓)
- `logo.png` - Any size, used in config flow (we have 270x270 ✓)
- PNG format with transparency if applicable

