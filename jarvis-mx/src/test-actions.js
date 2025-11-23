// src/test-actions.js
import { CommandAction, AdjustmentAction } from '@logitech/plugin-sdk';
import { exec } from 'node:child_process';

const BACKEND_URL = 'http://localhost:8000/console/action';

// Helper to POST to FastAPI
async function sendToBackend(payload) {
  try {
    const res = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    try {
      return await res.json();
    } catch {
      return {};
    }
  } catch (err) {
    console.error('Error sending to backend:', err);
    return {};
  }
}

function logButtonsMetadata(result) {
  if (result && Array.isArray(result.buttons)) {
    console.log('Buttons for current scene:', result.buttons);
    // TODO: Update key labels/icons dynamically when SDK runtime updates are available.
  }
}

function openUrl(url) {
  if (!url) return;
  const command =
    process.platform === 'win32'
      ? `cmd /c start "" "${url}"`
      : process.platform === 'darwin'
      ? `open "${url}"`
      : `xdg-open "${url}"`;

  exec(command, (err) => {
    if (err) {
      console.error('Failed to open URL:', url, err);
    }
  });
}

// Talk toggle (single key)
export class TalkAction extends CommandAction {
  name = 'jarvis_talk';
  displayName = 'Talk';
  description = 'Start/stop voice interaction with Jarvis';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Talk pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'talk',
      event: 'press',
      action: 'talk',
    });
    console.log('Talk result from backend:', result);
    logButtonsMetadata(result);
  }
}

// Stop button (explicit stop)
export class StopAction extends CommandAction {
  name = 'jarvis_stop';
  displayName = 'Stop';
  description = 'Stop listening/TTs';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Stop pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'stop',
      event: 'press',
      action: 'stop',
    });
    console.log('Stop result from backend:', result);
  }
}

// Resource 1
export class Resource1Action extends CommandAction {
  name = 'jarvis_resource_1';
  displayName = 'Resource 1';
  description = 'Activate first resource (manual/video/etc.)';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Resource 1 pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'resource_1',
      event: 'press',
      action: 'resource_1',
    });
    console.log('Resource 1 result:', result);
    // result.url contains manual/video URL. Your UI can use this.
    if (result && result.url) {
      console.log('Opening Resource 1 URL:', result.url);
      openUrl(result.url);
    }
  }
}

// Resource 2
export class Resource2Action extends CommandAction {
  name = 'jarvis_resource_2';
  displayName = 'Resource 2';
  description = 'Activate second resource';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Resource 2 pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'resource_2',
      event: 'press',
      action: 'resource_2',
    });
    console.log('Resource 2 result:', result);
    if (result && result.url) {
      console.log('Opening Resource 2 URL:', result.url);
      openUrl(result.url);
    }
  }
}

// Resource 3
export class Resource3Action extends CommandAction {
  name = 'jarvis_resource_3';
  displayName = 'Resource 3';
  description = 'Activate third resource';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Resource 3 pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'resource_3',
      event: 'press',
      action: 'resource_3',
    });
    console.log('Resource 3 result:', result);
    if (result && result.url) {
      console.log('Opening Resource 3 URL:', result.url);
      openUrl(result.url);
    }
  }
}

// Resource 4 -> Segmentation toggle
export class Resource4Action extends CommandAction {
  name = 'jarvis_resource_4';
  displayName = 'Resource 4';
  description = 'Show or hide the segmentation overlay';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Resource 4 pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'resource_4',
      event: 'press',
      action: 'resource_4',
    });
    console.log('Resource 4 result:', result);
    if (result && result.error) {
      console.error('Segmentation toggle failed:', result.error);
    }
  }
}

// Dial: scroll components
export class ScrollComponentAdjustment extends AdjustmentAction {
  name = 'jarvis_scroll_component';
  displayName = 'Scroll Components';
  description = 'Rotate to change selected component';
  groupName = 'Jarvis';

  async execute(event) {
    const direction = event.tick > 0 ? 1 : -1;
    console.log('Jarvis: Scroll component', event.tick, 'dir', direction);

    const result = await sendToBackend({
      device: 'dialpad',
      control: 'dial',
      event: 'rotate',
      action: 'scroll_component',
      value: direction,
    });
    console.log('Scroll result:', result);
  }
}

export class PanelResizeAdjustment extends AdjustmentAction {
  name = 'jarvis_resize_panel';
  displayName = 'Resize Panel';
  description = 'Rotate to adjust panel width';
  groupName = 'Jarvis';

  async execute(event) {
    const direction = event.tick > 0 ? 1 : -1;
    console.log('Jarvis: Resize panel dial', direction);

    const result = await sendToBackend({
      device: 'dialpad',
      control: 'panel_dial',
      event: 'rotate',
      action: 'resize_panel',
      value: direction,
    });
    console.log('Resize panel result:', result);
  }
}
