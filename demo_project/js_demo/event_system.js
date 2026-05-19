/**
 * Event Emitter - 事件发射器
 * 实现观察者模式，支持事件订阅和发布
 */

class EventEmitter {
    constructor() {
        this.listeners = new Map();
    }

    on(eventName, callback) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }
        this.listeners.get(eventName).push(callback);
        return this;
    }

    off(eventName, callback) {
        const callbacks = this.listeners.get(eventName);
        if (callbacks) {
            this.listeners.set(eventName, callbacks.filter(cb => cb !== callback));
        }
        return this;
    }

    emit(eventName, ...args) {
        const callbacks = this.listeners.get(eventName);
        if (callbacks) {
            callbacks.forEach(callback => callback(...args));
        }
        return this;
    }

    removeAllListeners(eventName) {
        if (eventName) {
            this.listeners.delete(eventName);
        } else {
            this.listeners.clear();
        }
        return this;
    }
}

/**
 * EventBus - 全局事件总线
 * 单例模式，管理应用级事件通信
 */

class EventBus {
    constructor() {
        this.emitter = new EventEmitter();
        this.eventHistory = [];
        this.maxHistorySize = 100;
    }

    publish(eventName, payload) {
        this.eventHistory.push({ eventName, payload, timestamp: Date.now() });
        if (this.eventHistory.length > this.maxHistorySize) {
            this.eventHistory.shift();
        }
        this.emitter.emit(eventName, payload);
    }

    subscribe(eventName, callback) {
        this.emitter.on(eventName, callback);
        return () => this.emitter.off(eventName, callback);
    }

    getHistory(eventName) {
        if (eventName) {
            return this.eventHistory.filter(e => e.eventName === eventName);
        }
        return [...this.eventHistory];
    }
}

/**
 * StateManager - 状态管理器
 * 简单的响应式状态管理
 */

class StateManager {
    constructor(initialState) {
        this.state = initialState || {};
        this.emitter = new EventEmitter();
    }

    getState(key) {
        return key ? this.state[key] : { ...this.state };
    }

    setState(key, value) {
        const oldValue = this.state[key];
        this.state[key] = value;
        this.emitter.emit(`change:${key}`, value, oldValue);
        this.emitter.emit("change", key, value, oldValue);
    }

    onChange(key, callback) {
        if (key) {
            this.emitter.on(`change:${key}`, callback);
        } else {
            this.emitter.on("change", callback);
        }
        return () => this.emitter.off(`change:${key}`, callback);
    }
}

const globalBus = new EventBus();
const globalState = new StateManager({ connected: false, theme: "dark" });

export { EventEmitter, EventBus, StateManager, globalBus, globalState };
