import assert from "node:assert";
import {
	getBrowserStackCredentials,
	isBrowserStackConfigured,
	parseBrowserStackDeviceId,
	BrowserStackManager,
	BrowserStackRobot,
} from "../src/browserstack";

describe("browserstack", () => {

	describe("getBrowserStackCredentials", () => {
		const originalUsername = process.env.BROWSERSTACK_USERNAME;
		const originalAccessKey = process.env.BROWSERSTACK_ACCESS_KEY;

		afterEach(() => {
			// Restore original env vars
			if (originalUsername !== undefined) {
				process.env.BROWSERSTACK_USERNAME = originalUsername;
			} else {
				delete process.env.BROWSERSTACK_USERNAME;
			}
			if (originalAccessKey !== undefined) {
				process.env.BROWSERSTACK_ACCESS_KEY = originalAccessKey;
			} else {
				delete process.env.BROWSERSTACK_ACCESS_KEY;
			}
		});

		it("should return null when BROWSERSTACK_USERNAME is not set", () => {
			delete process.env.BROWSERSTACK_USERNAME;
			delete process.env.BROWSERSTACK_ACCESS_KEY;
			const credentials = getBrowserStackCredentials();
			assert.strictEqual(credentials, null);
		});

		it("should return null when BROWSERSTACK_ACCESS_KEY is not set", () => {
			process.env.BROWSERSTACK_USERNAME = "testuser";
			delete process.env.BROWSERSTACK_ACCESS_KEY;
			const credentials = getBrowserStackCredentials();
			assert.strictEqual(credentials, null);
		});

		it("should return null when both env vars are empty strings", () => {
			process.env.BROWSERSTACK_USERNAME = "";
			process.env.BROWSERSTACK_ACCESS_KEY = "";
			const credentials = getBrowserStackCredentials();
			assert.strictEqual(credentials, null);
		});

		it("should return credentials when both env vars are set", () => {
			process.env.BROWSERSTACK_USERNAME = "testuser";
			process.env.BROWSERSTACK_ACCESS_KEY = "testaccesskey123";
			const credentials = getBrowserStackCredentials();
			assert.deepStrictEqual(credentials, {
				username: "testuser",
				accessKey: "testaccesskey123",
			});
		});
	});

	describe("isBrowserStackConfigured", () => {
		const originalUsername = process.env.BROWSERSTACK_USERNAME;
		const originalAccessKey = process.env.BROWSERSTACK_ACCESS_KEY;

		afterEach(() => {
			if (originalUsername !== undefined) {
				process.env.BROWSERSTACK_USERNAME = originalUsername;
			} else {
				delete process.env.BROWSERSTACK_USERNAME;
			}
			if (originalAccessKey !== undefined) {
				process.env.BROWSERSTACK_ACCESS_KEY = originalAccessKey;
			} else {
				delete process.env.BROWSERSTACK_ACCESS_KEY;
			}
		});

		it("should return false when credentials are not configured", () => {
			delete process.env.BROWSERSTACK_USERNAME;
			delete process.env.BROWSERSTACK_ACCESS_KEY;
			assert.strictEqual(isBrowserStackConfigured(), false);
		});

		it("should return true when credentials are configured", () => {
			process.env.BROWSERSTACK_USERNAME = "testuser";
			process.env.BROWSERSTACK_ACCESS_KEY = "testaccesskey123";
			assert.strictEqual(isBrowserStackConfigured(), true);
		});
	});

	describe("parseBrowserStackDeviceId", () => {
		it("should return null for non-browserstack device IDs", () => {
			assert.strictEqual(parseBrowserStackDeviceId("emulator-5554"), null);
			assert.strictEqual(parseBrowserStackDeviceId("00008101-001234567890"), null);
			assert.strictEqual(parseBrowserStackDeviceId(""), null);
		});

		it("should return null for malformed browserstack IDs", () => {
			assert.strictEqual(parseBrowserStackDeviceId("browserstack:"), null);
			assert.strictEqual(parseBrowserStackDeviceId("browserstack:ios"), null);
			assert.strictEqual(parseBrowserStackDeviceId("browserstack:ios:iPhone"), null);
			assert.strictEqual(parseBrowserStackDeviceId("browserstack:ios:iPhone:16:extra"), null);
		});

		it("should parse valid iOS device ID", () => {
			const result = parseBrowserStackDeviceId("browserstack:ios:iPhone 14 Pro:16");
			assert.deepStrictEqual(result, {
				os: "ios",
				device: "iPhone 14 Pro",
				osVersion: "16",
			});
		});

		it("should parse valid Android device ID", () => {
			const result = parseBrowserStackDeviceId("browserstack:android:Samsung Galaxy S23:13.0");
			assert.deepStrictEqual(result, {
				os: "android",
				device: "Samsung Galaxy S23",
				osVersion: "13.0",
			});
		});
	});

	describe("BrowserStackManager", () => {
		const mockCredentials = { username: "testuser", accessKey: "testaccesskey" };

		describe("getAuthHeader", () => {
			it("should generate correct Basic auth header", () => {
				const manager = new BrowserStackManager(mockCredentials);
				// Access private method through prototype for testing
				const authHeader = (manager as any).getAuthHeader();
				const expected = "Basic " + Buffer.from("testuser:testaccesskey").toString("base64");
				assert.strictEqual(authHeader, expected);
			});
		});

		describe("getAvailableDevices", () => {
			it("should transform API response to BrowserStackDevice format", async () => {
				const manager = new BrowserStackManager(mockCredentials);

				// Mock fetch
				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					assert.ok(url.toString().includes("app-automate/devices.json"));
					assert.strictEqual(options.headers.Authorization, (manager as any).getAuthHeader());

					return {
						ok: true,
						json: async () => [
							{ device: "iPhone 14", os: "ios", os_version: "16", realMobile: true },
							{ device: "Samsung Galaxy S23", os: "android", os_version: "13.0", realMobile: true },
						],
					} as Response;
				};

				try {
					const devices = await manager.getAvailableDevices();
					assert.strictEqual(devices.length, 2);

					assert.deepStrictEqual(devices[0], {
						id: "browserstack:ios:iPhone 14:16",
						device: "iPhone 14",
						os: "ios",
						os_version: "16",
						realMobile: true,
					});

					assert.deepStrictEqual(devices[1], {
						id: "browserstack:android:Samsung Galaxy S23:13.0",
						device: "Samsung Galaxy S23",
						os: "android",
						os_version: "13.0",
						realMobile: true,
					});
				} finally {
					global.fetch = originalFetch;
				}
			});

			it("should throw ActionableError on API failure", async () => {
				const manager = new BrowserStackManager(mockCredentials);

				const originalFetch = global.fetch;
				global.fetch = async () => {
					return { ok: false, status: 401 } as Response;
				};

				try {
					await assert.rejects(
						() => manager.getAvailableDevices(),
						/Failed to fetch BrowserStack devices: 401/
					);
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("createSession", () => {
			it("should create session with correct capabilities", async () => {
				const manager = new BrowserStackManager(mockCredentials);
				let capturedBody: any = null;

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (url.toString().includes("/session")) {
						capturedBody = JSON.parse(options.body);
						return {
							ok: true,
							json: async () => ({ value: { sessionId: "test-session-123" } }),
						} as Response;
					}
					return { ok: false, status: 404 } as Response;
				};

				try {
					const sessionId = await manager.createSession("iPhone 14", "ios", "16", "bs://app123");

					assert.strictEqual(sessionId, "test-session-123");
					assert.strictEqual(capturedBody.capabilities.alwaysMatch.platformName, "iOS");
					assert.strictEqual(capturedBody.capabilities.alwaysMatch["bstack:options"].deviceName, "iPhone 14");
					assert.strictEqual(capturedBody.capabilities.alwaysMatch["bstack:options"].osVersion, "16");
					assert.strictEqual(capturedBody.capabilities.alwaysMatch["bstack:options"].appUrl, "bs://app123");
				} finally {
					global.fetch = originalFetch;
				}
			});

			it("should use Android platform name for android OS", async () => {
				const manager = new BrowserStackManager(mockCredentials);
				let capturedBody: any = null;

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					capturedBody = JSON.parse(options.body);
					return {
						ok: true,
						json: async () => ({ value: { sessionId: "test-session-456" } }),
					} as Response;
				};

				try {
					await manager.createSession("Samsung Galaxy S23", "android", "13.0");
					assert.strictEqual(capturedBody.capabilities.alwaysMatch.platformName, "Android");
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("deleteSession", () => {
			it("should send DELETE request to session endpoint", async () => {
				const manager = new BrowserStackManager(mockCredentials);
				let deleteCalled = false;
				let deleteUrl = "";

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (options.method === "DELETE") {
						deleteCalled = true;
						deleteUrl = url.toString();
					}
					return { ok: true } as Response;
				};

				try {
					await manager.deleteSession("session-to-delete");
					assert.strictEqual(deleteCalled, true);
					assert.ok(deleteUrl.includes("session/session-to-delete"));
				} finally {
					global.fetch = originalFetch;
				}
			});
		});
	});

	describe("BrowserStackRobot", () => {
		const mockCredentials = { username: "testuser", accessKey: "testaccesskey" };
		const mockSessionId = "test-session-id";

		describe("getScreenSize", () => {
			it("should return screen dimensions from window/rect endpoint", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);

				const originalFetch = global.fetch;
				global.fetch = async (url: any) => {
					if (url.toString().includes("/window/rect")) {
						return {
							ok: true,
							text: async () => JSON.stringify({ value: { width: 390, height: 844 } }),
						} as Response;
					}
					return { ok: false, status: 404, text: async () => "Not found" } as Response;
				};

				try {
					const size = await robot.getScreenSize();
					assert.deepStrictEqual(size, { width: 390, height: 844, scale: 1 });
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("tap", () => {
			it("should send pointer actions to tap at coordinates", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);
				let capturedActions: any = null;

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (url.toString().includes("/actions") && options.method === "POST") {
						capturedActions = JSON.parse(options.body);
					}
					return { ok: true, text: async () => "" } as Response;
				};

				try {
					await robot.tap(100, 200);

					assert.ok(capturedActions);
					assert.strictEqual(capturedActions.actions[0].type, "pointer");
					assert.strictEqual(capturedActions.actions[0].parameters.pointerType, "touch");

					const pointerActions = capturedActions.actions[0].actions;
					const moveAction = pointerActions.find((a: any) => a.type === "pointerMove");
					assert.strictEqual(moveAction.x, 100);
					assert.strictEqual(moveAction.y, 200);
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("getScreenshot", () => {
			it("should return decoded base64 screenshot", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);
				const testImageBase64 = Buffer.from("fake-png-data").toString("base64");

				const originalFetch = global.fetch;
				global.fetch = async (url: any) => {
					if (url.toString().includes("/screenshot")) {
						return {
							ok: true,
							text: async () => JSON.stringify({ value: testImageBase64 }),
						} as Response;
					}
					return { ok: false, status: 404, text: async () => "Not found" } as Response;
				};

				try {
					const screenshot = await robot.getScreenshot();
					assert.ok(Buffer.isBuffer(screenshot));
					assert.strictEqual(screenshot.toString(), "fake-png-data");
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("sendKeys", () => {
			it("should send keys to active element", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);
				let keysPayload: any = null;

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (url.toString().includes("/element/active")) {
						return {
							ok: true,
							text: async () => JSON.stringify({ value: { ELEMENT: "elem-123" } }),
						} as Response;
					}
					if (url.toString().includes("/element/elem-123/value")) {
						keysPayload = JSON.parse(options.body);
						return { ok: true, text: async () => "" } as Response;
					}
					return { ok: true, text: async () => "" } as Response;
				};

				try {
					await robot.sendKeys("hello");
					assert.deepStrictEqual(keysPayload.value, ["h", "e", "l", "l", "o"]);
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("close", () => {
			it("should send DELETE request to close session", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);
				let deleteUrl = "";

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (options.method === "DELETE") {
						deleteUrl = url.toString();
					}
					return { ok: true, text: async () => "" } as Response;
				};

				try {
					await robot.close();
					assert.ok(deleteUrl.includes(`/session/${mockSessionId}`));
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("setOrientation", () => {
			it("should set orientation to uppercase", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);
				let orientationPayload: any = null;

				const originalFetch = global.fetch;
				global.fetch = async (url: any, options: any) => {
					if (url.toString().includes("/orientation") && options.method === "POST") {
						orientationPayload = JSON.parse(options.body);
					}
					return { ok: true, text: async () => "" } as Response;
				};

				try {
					await robot.setOrientation("landscape");
					assert.strictEqual(orientationPayload.orientation, "LANDSCAPE");
				} finally {
					global.fetch = originalFetch;
				}
			});
		});

		describe("getOrientation", () => {
			it("should return orientation as lowercase", async () => {
				const robot = new BrowserStackRobot(mockCredentials, mockSessionId);

				const originalFetch = global.fetch;
				global.fetch = async (url: any) => {
					if (url.toString().includes("/orientation")) {
						return {
							ok: true,
							text: async () => JSON.stringify({ value: "PORTRAIT" }),
						} as Response;
					}
					return { ok: false, status: 404, text: async () => "Not found" } as Response;
				};

				try {
					const orientation = await robot.getOrientation();
					assert.strictEqual(orientation, "portrait");
				} finally {
					global.fetch = originalFetch;
				}
			});
		});
	});
});
