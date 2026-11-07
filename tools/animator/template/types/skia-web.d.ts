/** Browser-only surface consumed by Skia's declarations. Native globals and
 * Reanimated clocks are deliberately absent: Remotion owns the frame clock.
 * These structural types describe Platform.web's DOM view and SharedValue data.
 */
declare module 'react-native' {
  import type {ComponentType, CSSProperties, ReactNode} from 'react';
  export type NodeHandle = number;
  export const Image: {resolveAssetSource(source: number): {uri: string}};
  export const PixelRatio: {get(): number};
  export const Platform: {OS: 'web'};
  export type MeasureOnSuccessCallback = (x: number, y: number, width: number, height: number, pageX: number, pageY: number) => void;
  export type MeasureInWindowOnSuccessCallback = (x: number, y: number, width: number, height: number) => void;
  export interface LayoutChangeEvent {nativeEvent: {layout: {x: number; y: number; width: number; height: number}}}
  export interface ViewProps {
    children?: ReactNode;
    style?: CSSProperties;
    nativeID?: string;
    pointerEvents?: 'auto' | 'none' | 'box-none' | 'box-only';
    onLayout?: (event: {nativeEvent: {layout: {x: number; y: number; width: number; height: number}}}) => void;
  }
  export type HostComponent<Props> = ComponentType<Props>;
  export const ViewComponent: ComponentType<ViewProps>;
  export const View: typeof ViewComponent;
  export function findNodeHandle(component: unknown): NodeHandle | null;
}
declare module 'react-native/Libraries/Types/CodegenTypes' {
  export type WithDefault<Type, Default extends Type> = Type | undefined;
}
declare module 'react-native/Libraries/TurboModule/RCTExport' {
  export interface TurboModule {getConstants?: () => object}
}
declare module 'react-native-reanimated' {
  export interface SharedValue<Value = unknown> {
    value: Value;
    get(): Value;
    set(value: Value | ((value: Value) => Value)): void;
    addListener(listenerID: number, listener: (value: Value) => void): void;
    removeListener(listenerID: number): void;
    modify(modifier?: (value: Value) => Value, forceUpdate?: boolean): void;
  }
  export type ExtrapolationType = 'identity' | 'clamp' | 'extend' | {
    extrapolateLeft?: 'identity' | 'clamp' | 'extend';
    extrapolateRight?: 'identity' | 'clamp' | 'extend';
  } | undefined;
}
declare module 'react-native-reanimated/lib/typescript/commonTypes' {
  import type {SharedValue} from 'react-native-reanimated';
  export interface Mutable<Value = unknown> extends SharedValue<Value> {
    _isReanimatedSharedValue: true;
    _value: Value;
  }
}
