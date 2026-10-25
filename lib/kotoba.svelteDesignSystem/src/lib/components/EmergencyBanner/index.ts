import type { ComponentProps } from 'svelte';
import EmergencyBannerHeadingComponent from './EmergencyBannerHeading.svelte';

export { default as EmergencyBanner } from './EmergencyBanner.svelte';
export { default as EmergencyBannerHeading } from './EmergencyBannerHeading.svelte';
export type EmergencyBannerHeadingLevel = ComponentProps<typeof EmergencyBannerHeadingComponent>['level'];
export { default as EmergencyBannerBody } from './EmergencyBannerBody.svelte';
export { default as EmergencyBannerButton } from './EmergencyBannerButton.svelte';
export { bannerBodyStyle } from './styles';
