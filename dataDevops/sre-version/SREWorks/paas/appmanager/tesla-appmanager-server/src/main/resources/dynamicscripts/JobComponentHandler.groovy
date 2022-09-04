package dynamicscripts

import com.alibaba.tesla.appmanager.server.dynamicscript.handler.ComponentHandler

/**
 * Job 类型组件
 *
 * @author yaoxing.gyx@alibaba-inc.com
 */
class JobComponentHandler implements ComponentHandler {

    /**
     * Handler 元信息
     */
    public static final String KIND = "COMPONENT"
    public static final String NAME = "K8S_JOB"
    public static final Integer REVISION = 4

    /**
     * 获取 `COMPONENT_BUILD` 类型下的映射名称
     *
     * @return 示例：`JobDefault`
     */
    @Override
    String buildScriptName() {
        return "JobDefault"
    }

    /**
     * 获取 `COMPONENT_DEPLOY` 类型下的映射名称
     *
     * @return 示例：`JobDefault` / `HelmDefault`
     */
    @Override
    String deployScriptName() {
        return "JobDefault"
    }

    /**
     * 获取 `COMPONENT_DESTROY` 类型下的映射名称
     *
     * @return 示例：`HelmDefault`
     */
    @Override
    String destroyName() {
        return "JobDefault"
    }

    /**
     * 获取状态监听类型
     *
     * @return 返回 `KUBERNETES_INFORMER` 或 `CRON`
     */
    @Override
    String watchKind() {
        return "KUBERNETES_INFORMER"
    }

    /**
     * 如果 `watchKind` 返回 `KUBERNETES_INFORMER`，则对应 `COMPONENT_WATCH_KUBERNETES_INFORMER` 类型下的映射名称
     * <p>
     * 如果 `watchKind` 返回 `CRON`，则对应 `COMPONENT_WATCH_CRON` 类型下的映射名称
     *
     * @return 返回对应类型下的映射名称
     */
    @Override
    String watchScriptName() {
        return "JobInformerRegister"
    }
}
