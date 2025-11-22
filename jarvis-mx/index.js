// index.js
import { PluginSDK } from '@logitech/plugin-sdk';
import {
  ScanAction,
  TalkAction,
  Resource1Action,
  Resource2Action,
  Resource3Action,
  ScrollComponentAdjustment,
} from './src/test-actions.js';

const pluginSDK = new PluginSDK();

pluginSDK.registerAction(new ScanAction());
pluginSDK.registerAction(new TalkAction());
pluginSDK.registerAction(new Resource1Action());
pluginSDK.registerAction(new Resource2Action());
pluginSDK.registerAction(new Resource3Action());
pluginSDK.registerAction(new ScrollComponentAdjustment());


await pluginSDK.connect();

console.log('Jarvis MX plugin connected');
