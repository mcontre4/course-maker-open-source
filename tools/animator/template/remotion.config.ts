import {Config} from '@remotion/cli/config';
import {enableSkia} from '@remotion/skia/enable';
Config.overrideWebpackConfig(config => enableSkia({...config, resolve: {...config.resolve,
  alias: {...config.resolve?.alias, 'react-native$': 'react-native-web'}}}));
