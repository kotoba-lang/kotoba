/** Headless toast manager — Svelte 5 runes-based */
export interface ToastItem {
	id: string;
	message: string;
	type: 'info' | 'success' | 'warning' | 'error';
	duration: number;
}

export interface CreateToastOpts {
	defaultDuration?: number;
	maxToasts?: number;
}

let counter = 0;

export function createToast(opts: CreateToastOpts = {}) {
	const defaultDuration = opts.defaultDuration ?? 3000;
	const maxToasts = opts.maxToasts ?? 5;
	let items = $state<ToastItem[]>([]);
	const timers = new Map<string, ReturnType<typeof setTimeout>>();

	function add(message: string, type: ToastItem['type'] = 'info', duration?: number) {
		const id = `toast-${++counter}`;
		const d = duration ?? defaultDuration;
		const item: ToastItem = { id, message, type, duration: d };

		items = [...items, item].slice(-maxToasts);

		if (d > 0) {
			timers.set(
				id,
				setTimeout(() => dismiss(id), d)
			);
		}

		return id;
	}

	function dismiss(id: string) {
		const timer = timers.get(id);
		if (timer) {
			clearTimeout(timer);
			timers.delete(id);
		}
		items = items.filter((t) => t.id !== id);
	}

	function clear() {
		for (const timer of timers.values()) clearTimeout(timer);
		timers.clear();
		items = [];
	}

	return {
		get toasts() {
			return items;
		},
		add,
		dismiss,
		clear
	};
}
