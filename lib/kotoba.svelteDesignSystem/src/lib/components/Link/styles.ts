export const linkDefaultStyle = 'text-blue-1000 underline underline-offset-[calc(3/16*1rem)]';
export const linkVisitedStyle = 'visited:text-magenta-900';
export const linkHoverStyle = 'hover:text-blue-1000 hover:decoration-[calc(3/16*1rem)]';
export const linkFocusStyle =
  'focus-visible:rounded-4 focus-visible:outline focus-visible:outline-4 focus-visible:outline-black focus-visible:outline-offset-[calc(2/16*1rem)] focus-visible:bg-yellow-300 focus-visible:text-blue-1000 focus-visible:ring-[calc(2/16*1rem)] focus-visible:ring-yellow-300';
export const linkActiveStyle = 'active:text-orange-800 active:decoration-1';

export const linkStyle = `
  ${linkDefaultStyle}
  ${linkVisitedStyle}
  ${linkHoverStyle}
  ${linkFocusStyle}
  ${linkActiveStyle}
`;
