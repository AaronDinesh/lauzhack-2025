// src/test-actions.js
import { CommandAction, AdjustmentAction } from '@logitech/plugin-sdk';

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

// K1: Scan 
export class ScanAction extends CommandAction {
  name = 'jarvis_scan';
  displayName = 'Scan';
  description = 'Analyse the scene and detect components';
  groupName = 'Jarvis';

  async onKeyDown(event) {
    console.log('Jarvis: Scan pressed');
    const result = await sendToBackend({
      device: 'keypad',
      control: 'scan',
      event: 'press',
      action: 'scan',
    });

    console.log('Scan result from backend:', result);

    // TODO: if you find in the SDK how to update key labels/icons,
    // this is where you’d loop over result.buttons and call
    // event.setTitle(...) / event.setImage(...).
  }
}

// K2: Talk
export class TalkAction extends CommandAction {
  name = 'jarvis_talk';
  displayName = 'Talk';
  description = 'Start voice interaction with Jarvis';
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
  }
}

//K3: Resource 1 
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
  }
}

//K4: Resource 2 
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
  }
}

//K5: Resource 3 
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
  }
}

//Dial: scroll components 
export class ScrollComponentAdjustment extends AdjustmentAction {
  name = 'jarvis_scroll_component';
  displayName = 'Scroll Components';
  description = 'Rotate to change selected component';
  groupName = 'Jarvis';

  async execute(event) {
    const direction = event.tick > 0 ? 1 : -1;
    console.log('Jarvis: Scroll component', event.tick, '→ dir', direction);

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
