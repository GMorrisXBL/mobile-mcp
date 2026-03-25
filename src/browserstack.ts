/**
 * BrowserStack App Automate integration for mobile-mcp
 *
 * This module provides a Robot implementation that connects to BrowserStack's
 * Appium hub to control remote real devices.
 *
 * Required environment variables:
 *   BROWSERSTACK_USERNAME - Your BrowserStack username
 *   BROWSERSTACK_ACCESS_KEY - Your BrowserStack access key
 *
 * Optional environment variables:
 *   BROWSERSTACK_APP_URL - URL of uploaded app (bs://xxx or app_url)
 */

import { ActionableError, Button, InstalledApp, Orientation, Robot, ScreenElement, ScreenSize, SwipeDirection } from "./robot";

const BROWSERSTACK_HUB = "https://hub-cloud.browserstack.com/wd/hub";
const BROWSERSTACK_API = "https://api-cloud.browserstack.com";

export interface BrowserStackCredentials {
	username: string;
	accessKey: string;
}

export interface BrowserStackDevice {
	id: string;
	device: string;
	os: string;
	os_version: string;
	realMobile: boolean;
}

export interface BrowserStackSession {
	sessionId: string;
	device: string;
	os: string;
	os_version: string;
}

/**
 * Get BrowserStack credentials from environment variables
 */
export function getBrowserStackCredentials(): BrowserStackCredentials | null {
	const username = process.env.BROWSERSTACK_USERNAME;
	const accessKey = process.env.BROWSERSTACK_ACCESS_KEY;

	if (!username || !accessKey) {
		return null;
	}

	return { username, accessKey };
}

/**
 * Check if BrowserStack is configured
 */
export function isBrowserStackConfigured(): boolean {
	return getBrowserStackCredentials() !== null;
}

/**
 * BrowserStack Device Manager - lists available devices and manages sessions
 */
export class BrowserStackManager {
	private credentials: BrowserStackCredentials;

	constructor(credentials: BrowserStackCredentials) {
		this.credentials = credentials;
	}

	private getAuthHeader(): string {
		const auth = Buffer.from(`${this.credentials.username}:${this.credentials.accessKey}`).toString("base64");
		return `Basic ${auth}`;
	}

	/**
	 * Get list of available devices from BrowserStack
	 */
	public async getAvailableDevices(): Promise<BrowserStackDevice[]> {
		const response = await fetch(`${BROWSERSTACK_API}/app-automate/devices.json`, {
			headers: {
				"Authorization": this.getAuthHeader(),
			},
		});

		if (!response.ok) {
			throw new ActionableError(`Failed to fetch BrowserStack devices: ${response.status}`);
		}

		const devices = await response.json() as Array<{
			device: string;
			os: string;
			os_version: string;
			realMobile: boolean;
		}>;

		return devices.map(d => ({
			id: `browserstack:${d.os}:${d.device}:${d.os_version}`,
			device: d.device,
			os: d.os,
			os_version: d.os_version,
			realMobile: d.realMobile,
		}));
	}

	/**
	 * Create a new Appium session on BrowserStack
	 */
	public async createSession(device: string, os: string, osVersion: string, appUrl?: string): Promise<string> {
		const capabilities: Record<string, any> = {
			"bstack:options": {
				userName: this.credentials.username,
				accessKey: this.credentials.accessKey,
				deviceName: device,
				osVersion: osVersion,
				realMobile: "true",
				local: "false",
				debug: "true",
				networkLogs: "true",
			},
			"platformName": os === "ios" ? "iOS" : "Android",
		};

		// Add app URL if provided
		const app = appUrl || process.env.BROWSERSTACK_APP_URL;
		if (app) {
			capabilities["bstack:options"].appUrl = app;
		}

		const response = await fetch(`${BROWSERSTACK_HUB}/session`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"Authorization": this.getAuthHeader(),
			},
			body: JSON.stringify({
				capabilities: {
					alwaysMatch: capabilities,
				},
			}),
		});

		if (!response.ok) {
			const errorText = await response.text();
			throw new ActionableError(`Failed to create BrowserStack session: ${response.status} ${errorText}`);
		}

		const result = await response.json() as { value: { sessionId: string } };
		return result.value.sessionId;
	}

	/**
	 * Delete a BrowserStack session
	 */
	public async deleteSession(sessionId: string): Promise<void> {
		await fetch(`${BROWSERSTACK_HUB}/session/${sessionId}`, {
			method: "DELETE",
			headers: {
				"Authorization": this.getAuthHeader(),
			},
		});
	}

	/**
	 * Upload an app to BrowserStack
	 */
	public async uploadApp(filePath: string): Promise<string> {
		const fs = await import("node:fs");
		const path = await import("node:path");

		const fileBuffer = fs.readFileSync(filePath);
		const fileName = path.basename(filePath);

		// Create multipart form data manually
		const boundary = `----WebKitFormBoundary${Date.now()}`;
		const body = Buffer.concat([
			Buffer.from(`--${boundary}\r\n`),
			Buffer.from(`Content-Disposition: form-data; name="file"; filename="${fileName}"\r\n`),
			Buffer.from(`Content-Type: application/octet-stream\r\n\r\n`),
			fileBuffer,
			Buffer.from(`\r\n--${boundary}--\r\n`),
		]);

		const response = await fetch(`${BROWSERSTACK_API}/app-automate/upload`, {
			method: "POST",
			headers: {
				"Authorization": this.getAuthHeader(),
				"Content-Type": `multipart/form-data; boundary=${boundary}`,
			},
			body: body,
		});

		if (!response.ok) {
			const errorText = await response.text();
			throw new ActionableError(`Failed to upload app to BrowserStack: ${response.status} ${errorText}`);
		}

		const result = await response.json() as { app_url: string };
		return result.app_url;
	}
}

/**
 * BrowserStack Robot - controls a remote device via BrowserStack's Appium hub
 */
export class BrowserStackRobot implements Robot {
	private credentials: BrowserStackCredentials;
	private sessionId: string;
	private hubUrl: string;

	constructor(credentials: BrowserStackCredentials, sessionId: string) {
		this.credentials = credentials;
		this.sessionId = sessionId;
		this.hubUrl = BROWSERSTACK_HUB;
	}

	private getAuthHeader(): string {
		const auth = Buffer.from(`${this.credentials.username}:${this.credentials.accessKey}`).toString("base64");
		return `Basic ${auth}`;
	}

	private async request(method: string, path: string, body?: any): Promise<any> {
		const url = `${this.hubUrl}/session/${this.sessionId}${path}`;
		const response = await fetch(url, {
			method,
			headers: {
				"Content-Type": "application/json",
				"Authorization": this.getAuthHeader(),
			},
			body: body ? JSON.stringify(body) : undefined,
		});

		if (!response.ok) {
			const errorText = await response.text();
			throw new ActionableError(`BrowserStack request failed: ${response.status} ${errorText}`);
		}

		const text = await response.text();
		if (!text) {return null;}

		return JSON.parse(text);
	}

	public async getScreenSize(): Promise<ScreenSize> {
		const result = await this.request("GET", "/window/rect");
		return {
			width: result.value.width,
			height: result.value.height,
			scale: 1, // BrowserStack returns actual pixels
		};
	}

	public async swipe(direction: SwipeDirection): Promise<void> {
		const screenSize = await this.getScreenSize();
		const centerX = Math.floor(screenSize.width / 2);
		const centerY = Math.floor(screenSize.height / 2);
		const distance = Math.floor(screenSize.height * 0.4);

		let startX = centerX, startY = centerY, endX = centerX, endY = centerY;

		switch (direction) {
			case "up":
				startY = centerY + distance / 2;
				endY = centerY - distance / 2;
				break;
			case "down":
				startY = centerY - distance / 2;
				endY = centerY + distance / 2;
				break;
			case "left":
				startX = centerX + distance / 2;
				endX = centerX - distance / 2;
				break;
			case "right":
				startX = centerX - distance / 2;
				endX = centerX + distance / 2;
				break;
		}

		await this.performSwipe(startX, startY, endX, endY);
	}

	public async swipeFromCoordinate(x: number, y: number, direction: SwipeDirection, distance: number = 400): Promise<void> {
		let endX = x, endY = y;

		switch (direction) {
			case "up":
				endY = y - distance;
				break;
			case "down":
				endY = y + distance;
				break;
			case "left":
				endX = x - distance;
				break;
			case "right":
				endX = x + distance;
				break;
		}

		await this.performSwipe(x, y, endX, endY);
	}

	private async performSwipe(startX: number, startY: number, endX: number, endY: number): Promise<void> {
		await this.request("POST", "/actions", {
			actions: [
				{
					type: "pointer",
					id: "finger1",
					parameters: { pointerType: "touch" },
					actions: [
						{ type: "pointerMove", duration: 0, x: startX, y: startY },
						{ type: "pointerDown", button: 0 },
						{ type: "pointerMove", duration: 1000, x: endX, y: endY },
						{ type: "pointerUp", button: 0 },
					],
				},
			],
		});

		// Clear actions
		await this.request("DELETE", "/actions");
	}

	public async getScreenshot(): Promise<Buffer> {
		const result = await this.request("GET", "/screenshot");
		return Buffer.from(result.value, "base64");
	}

	public async listApps(): Promise<InstalledApp[]> {
		// BrowserStack doesn't provide an API to list installed apps
		// Return empty array - user should know which apps they've uploaded
		return [];
	}

	public async launchApp(packageName: string, _locale?: string): Promise<void> {
		await this.request("POST", "/appium/device/activate_app", {
			bundleId: packageName, // iOS
			appPackage: packageName, // Android - Appium handles both
		});
	}

	public async terminateApp(packageName: string): Promise<void> {
		await this.request("POST", "/appium/device/terminate_app", {
			bundleId: packageName,
			appPackage: packageName,
		});
	}

	public async installApp(path: string): Promise<void> {
		// For BrowserStack, apps must be uploaded first via the API
		// The path should be a bs:// URL
		if (path.startsWith("bs://")) {
			await this.request("POST", "/appium/device/install_app", {
				appPath: path,
			});
		} else {
			throw new ActionableError(
				"BrowserStack requires apps to be uploaded first. Use the BrowserStack API to upload your app and get a bs:// URL."
			);
		}
	}

	public async uninstallApp(bundleId: string): Promise<void> {
		await this.request("POST", "/appium/device/remove_app", {
			bundleId: bundleId,
			appPackage: bundleId,
		});
	}

	public async openUrl(url: string): Promise<void> {
		await this.request("POST", "/url", { url });
	}

	public async sendKeys(text: string): Promise<void> {
		// Find the active element and send keys to it
		const activeElement = await this.request("POST", "/element/active");
		if (activeElement?.value?.ELEMENT) {
			await this.request("POST", `/element/${activeElement.value.ELEMENT}/value`, {
				value: text.split(""),
			});
		} else {
			// Fallback: use keyboard actions
			await this.request("POST", "/actions", {
				actions: [{
					type: "key",
					id: "keyboard",
					actions: text.split("").flatMap(char => [
						{ type: "keyDown", value: char },
						{ type: "keyUp", value: char },
					]),
				}],
			});
		}
	}

	public async pressButton(button: Button): Promise<void> {
		const buttonMap: Record<string, string> = {
			"HOME": "home",
			"BACK": "back",
			"VOLUME_UP": "volumeup",
			"VOLUME_DOWN": "volumedown",
			"ENTER": "\n",
		};

		if (button === "ENTER") {
			await this.sendKeys("\n");
			return;
		}

		const mappedButton = buttonMap[button];
		if (!mappedButton) {
			throw new ActionableError(`Button "${button}" is not supported on BrowserStack`);
		}

		// Use mobile:pressButton for iOS or keyevent for Android
		try {
			await this.request("POST", "/appium/device/press_button", {
				name: mappedButton,
			});
		} catch {
			// Fallback for Android
			const keyCodeMap: Record<string, number> = {
				"home": 3,
				"back": 4,
				"volumeup": 24,
				"volumedown": 25,
			};
			const keyCode = keyCodeMap[mappedButton];
			if (keyCode) {
				await this.request("POST", "/appium/device/press_keycode", {
					keycode: keyCode,
				});
			}
		}
	}

	public async tap(x: number, y: number): Promise<void> {
		await this.request("POST", "/actions", {
			actions: [
				{
					type: "pointer",
					id: "finger1",
					parameters: { pointerType: "touch" },
					actions: [
						{ type: "pointerMove", duration: 0, x, y },
						{ type: "pointerDown", button: 0 },
						{ type: "pause", duration: 100 },
						{ type: "pointerUp", button: 0 },
					],
				},
			],
		});
	}

	public async doubleTap(x: number, y: number): Promise<void> {
		await this.request("POST", "/actions", {
			actions: [
				{
					type: "pointer",
					id: "finger1",
					parameters: { pointerType: "touch" },
					actions: [
						{ type: "pointerMove", duration: 0, x, y },
						{ type: "pointerDown", button: 0 },
						{ type: "pause", duration: 50 },
						{ type: "pointerUp", button: 0 },
						{ type: "pause", duration: 100 },
						{ type: "pointerDown", button: 0 },
						{ type: "pause", duration: 50 },
						{ type: "pointerUp", button: 0 },
					],
				},
			],
		});
	}

	public async longPress(x: number, y: number, duration: number): Promise<void> {
		await this.request("POST", "/actions", {
			actions: [
				{
					type: "pointer",
					id: "finger1",
					parameters: { pointerType: "touch" },
					actions: [
						{ type: "pointerMove", duration: 0, x, y },
						{ type: "pointerDown", button: 0 },
						{ type: "pause", duration },
						{ type: "pointerUp", button: 0 },
					],
				},
			],
		});
	}

	public async getElementsOnScreen(): Promise<ScreenElement[]> {
		// Get page source and parse elements
		await this.request("GET", "/source");

		// Parse XML/JSON source to extract elements
		// BrowserStack returns Appium-format source
		const elements: ScreenElement[] = [];

		try {
			// Try to find elements using Appium's find elements
			const allElements = await this.request("POST", "/elements", {
				using: "xpath",
				value: "//*[@clickable='true' or @type='XCUIElementTypeButton' or @type='XCUIElementTypeTextField' or @type='XCUIElementTypeStaticText']",
			});

			if (allElements?.value) {
				for (const elem of allElements.value) {
					const elementId = elem.ELEMENT || elem["element-6066-11e4-a52e-4f735466cecf"];
					if (!elementId) {continue;}

					try {
						const [rect, text, label] = await Promise.all([
							this.request("GET", `/element/${elementId}/rect`),
							this.request("GET", `/element/${elementId}/text`).catch(() => ({ value: "" })),
							this.request("GET", `/element/${elementId}/attribute/label`).catch(() => ({ value: "" })),
						]);

						elements.push({
							type: "element",
							text: text?.value || "",
							label: label?.value || "",
							rect: {
								x: rect.value.x,
								y: rect.value.y,
								width: rect.value.width,
								height: rect.value.height,
							},
						});
					} catch {
						// Skip elements that can't be inspected
					}
				}
			}
		} catch (error) {
			// Fallback: return empty array if element inspection fails
		}

		return elements;
	}

	public async setOrientation(orientation: Orientation): Promise<void> {
		await this.request("POST", "/orientation", {
			orientation: orientation.toUpperCase(),
		});
	}

	public async getOrientation(): Promise<Orientation> {
		const result = await this.request("GET", "/orientation");
		return result.value.toLowerCase() as Orientation;
	}

	/**
	 * Close the BrowserStack session
	 */
	public async close(): Promise<void> {
		await this.request("DELETE", "");
	}
}

/**
 * Parse a BrowserStack device ID back to its components
 */
export function parseBrowserStackDeviceId(deviceId: string): { os: string; device: string; osVersion: string } | null {
	if (!deviceId.startsWith("browserstack:")) {
		return null;
	}

	const parts = deviceId.split(":");
	if (parts.length !== 4) {
		return null;
	}

	return {
		os: parts[1],
		device: parts[2],
		osVersion: parts[3],
	};
}
