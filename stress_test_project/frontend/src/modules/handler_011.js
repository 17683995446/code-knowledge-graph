
/**
 * handler_011 - 转换数据的核心模块
 * @module handler_011
 */

/**
 * 状态枚举
 * @enum {string}
 */
const Handler011KKUStatus = {
    PENDING: 'pending',
    ACTIVE: 'active',
    COMPLETED: 'completed',
    FAILED: 'failed',
    CANCELLED: 'cancelled'
};

/**
 * 默认配置
 * @type {Object}
 */
const DEFAULT_CONFIG = {
    name: 'default',
    value: 0,
    enabled: true,
    priority: 0
};

/**
 * Handler011KKU类
 * @class
 */
class Handler011KKU {
    /**
     * 构造函数
     * @param {Object} config - 配置对象
     */
    constructor(config = DEFAULT_CONFIG) {
        this.config = { ...DEFAULT_CONFIG, ...config };
        this._status = Handler011KKUStatus.PENDING;
        this._data = [];
        this._callbacks = [];
    }

    /**
     * 获取状态
     * @returns {string} 当前状态
     */
    get status() {
        return this._status;
    }

    /**
     * 检查是否激活
     * @returns {boolean}
     */
    isActive() {
        return this._status === Handler011KKUStatus.ACTIVE;
    }

    /**
     * 初始化
     * @returns {boolean} 是否成功
     */
    initialize() {
        try {
            this._status = Handler011KKUStatus.ACTIVE;
            console.log(`${this.constructor.name} initialized`);
            return true;
        } catch (error) {
            console.error('Initialization failed:', error);
            this._status = Handler011KKUStatus.FAILED;
            return false;
        }
    }

    /**
     * 处理数据
     * @param {Array} data - 输入数据
     * @returns {Object} 处理结果
     */
    process(data) {
        if (!this.isActive()) {
            throw new Error('Processor is not active');
        }

        const results = data.map(item => this._processItem(item));
        this._data.push(...results);
        this._notifyCallbacks();

        return {
            processedCount: results.length,
            status: 'success'
        };
    }

    /**
     * 处理单个项目
     * @private
     * @param {Object} item - 数据项
     * @returns {Object} 处理后的数据
     */
    _processItem(item) {
        return {
            ...item,
            processedAt: Date.now(),
            processor: this.constructor.name
        };
    }

    /**
     * 通知回调
     * @private
     */
    _notifyCallbacks() {
        this._callbacks.forEach(callback => {
            try {
                callback(this._data);
            } catch (error) {
                console.warn('Callback failed:', error);
            }
        });
    }

    /**
     * 注册回调
     * @param {Function} callback - 回调函数
     */
    registerCallback(callback) {
        this._callbacks.push(callback);
    }

    /**
     * 清理资源
     */
    cleanup() {
        this._data = [];
        this._callbacks = [];
        this._status = Handler011KKUStatus.COMPLETED;
    }

    /**
     * 导出结果
     * @returns {Object} JSON数据
     */
    exportResults() {
        return JSON.stringify(this._data, null, 2);
    }

    /**
     * 验证数据
     * @static
     * @param {Object} data - 待验证数据
     * @returns {boolean}
     */
    static validateData(data) {
        const requiredFields = ['id', 'name', 'type'];
        return requiredFields.every(field => field in data);
    }
}

/**
 * 工厂类
 */
class Handler011KKUFactory {
    static _instances = new Map();

    static create(name, config = null) {
        if (this._instances.has(name)) {
            return this._instances.get(name);
        }

        const instance = new Handler011KKU(config);
        this._instances.set(name, instance);
        return instance;
    }

    static getInstance(name) {
        return this._instances.get(name);
    }

    static removeInstance(name) {
        return this._instances.delete(name);
    }

    static clearAll() {
        this._instances.clear();
    }
}

/**
 * 创建默认实例
 * @returns {Handler011KKU}
 */
function createDefaultHandler011KKU() {
    const config = { name: 'default', value: 100, priority: 1 };
    return Handler011KKUFactory.create('default', config);
}

export { Handler011KKU, Handler011KKUFactory, Handler011KKUStatus, createDefaultHandler011KKU };
