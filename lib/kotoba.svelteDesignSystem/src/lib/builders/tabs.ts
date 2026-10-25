/** Headless tabs builder — returns ARIA attrs and keyboard navigation */
export interface CreateTabsOpts {
	defaultValue?: string;
	onValueChange?: (value: string) => void;
}

export function createTabs(opts: CreateTabsOpts = {}) {
	let activeValue = $state(opts.defaultValue ?? '');

	function setValue(value: string) {
		activeValue = value;
		opts.onValueChange?.(value);
	}

	function triggerAttrs(value: string) {
		return {
			role: 'tab' as const,
			'aria-selected': activeValue === value,
			tabindex: activeValue === value ? 0 : -1,
			onclick: () => setValue(value),
			onkeydown: (e: KeyboardEvent) => {
				if (e.key === 'Enter' || e.key === ' ') {
					e.preventDefault();
					setValue(value);
				}
			}
		};
	}

	function contentAttrs(value: string) {
		return {
			role: 'tabpanel' as const,
			hidden: activeValue !== value,
			tabindex: 0
		};
	}

	function listAttrs() {
		return {
			role: 'tablist' as const
		};
	}

	return {
		get value() {
			return activeValue;
		},
		set value(v: string) {
			setValue(v);
		},
		trigger: triggerAttrs,
		content: contentAttrs,
		list: listAttrs
	};
}
