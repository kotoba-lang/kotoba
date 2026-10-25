export type ButtonVariant = 'solid-fill' | 'outline' | 'text';
export type ButtonSize = 'lg' | 'md' | 'sm' | 'xs';

export const buttonBaseStyle = `
  underline-offset-[calc(3/16*1rem)]
  transition-transform duration-100 active:scale-[0.97]
  focus-visible:outline focus-visible:outline-4 focus-visible:outline-gv2-text-primary focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300
  aria-disabled:pointer-events-none aria-disabled:forced-colors:border-[GrayText] aria-disabled:forced-colors:text-[GrayText]
`;

export const buttonVariantStyle: Record<ButtonVariant, string> = {
  'solid-fill': `
    border-4
    border-double
    border-transparent
    bg-blue-900
    text-white
    hover:bg-blue-1000
    hover:underline
    active:bg-blue-1200
    active:underline
    aria-disabled:bg-solid-gray-300
    aria-disabled:text-solid-gray-50
  `,
  outline: `
    border
    border-current
    bg-gv2-bg-input
    text-blue-900
    hover:bg-blue-200
    hover:text-blue-1000
    hover:underline
    active:bg-blue-300
    active:text-blue-1200
    active:underline
    aria-disabled:bg-gv2-bg-input
    aria-disabled:text-solid-gray-300
  `,
  text: `
    text-blue-900
    underline
    hover:bg-blue-50
    hover:text-blue-1000
    hover:decoration-[calc(3/16*1rem)]
    active:bg-blue-100
    active:text-blue-1200
    focus-visible:bg-yellow-300
    aria-disabled:bg-transparent
    aria-disabled:focus-visible:bg-yellow-300
    aria-disabled:text-solid-gray-300
  `,
};

export const buttonSizeStyle: Record<ButtonSize, string> = {
  lg: 'min-w-[calc(136/16*1rem)] min-h-14 rounded-8 px-4 py-3 text-oln-16B-100',
  md: 'min-w-24 min-h-12 rounded-8 px-4 py-2 text-oln-16B-100',
  sm: 'relative min-w-20 min-h-9 rounded-6 px-3 py-0.5 text-oln-16B-100 after:absolute after:inset-x-0 after:-inset-y-full after:m-auto after:h-[44px]',
  xs: 'relative min-w-18 min-h-7 rounded-4 px-2 py-0.5 text-oln-14B-100 after:absolute after:inset-x-0 after:-inset-y-full after:m-auto after:h-[44px]',
};
