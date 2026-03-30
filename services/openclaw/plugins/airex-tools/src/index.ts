type JsonSchema = Record<string, unknown>;

type ToolRegistration = {
    name: string;
    description: string;
    parameters: JsonSchema;
    execute: (_id: string, params: Record<string, unknown>) => Promise<{
        content: Array<{ type: "text"; text: string }>;
    }>;
};

type PluginApi = {
    registerTool: (tool: ToolRegistration) => void;
};

const DEFAULT_AIREX_BASE_URL = "http://host.docker.internal:8000";
const DEFAULT_TIMEOUT_MS = 30_000;

function getAirexBaseUrl(): string {
    return process.env.AIREX_TOOLS_BASE_URL || DEFAULT_AIREX_BASE_URL;
}

function getToolTimeoutMs(): number {
    const parsed = Number.parseInt(process.env.AIREX_TOOL_TIMEOUT_MS || "", 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_TIMEOUT_MS;
}

function getAuthHeaders(): Record<string, string> {
    const token =
        process.env.OPENCLAW_TOOL_SERVER_TOKEN ||
        process.env.INTERNAL_TOOLS_TOKEN ||
        process.env.OPENCLAW_GATEWAY_TOKEN ||
        "";
    return token ? { "X-Internal-Tool-Token": token } : {};
}

async function callAirex(
    path: string,
    params: Record<string, unknown>,
): Promise<unknown> {
    const response = await fetch(
        `${getAirexBaseUrl()}/api/v1/internal/tools/${path}`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(),
            },
            body: JSON.stringify(params),
            signal: AbortSignal.timeout(getToolTimeoutMs()),
        },
    );

    const responseText = await response.text();
    let parsedBody: unknown = responseText;
    if (responseText) {
        try {
            parsedBody = JSON.parse(responseText);
        } catch {
            parsedBody = responseText;
        }
    }

    if (!response.ok) {
        const detail =
            typeof parsedBody === "object" && parsedBody !== null && "detail" in parsedBody
                ? String((parsedBody as { detail: unknown }).detail)
                : responseText || `HTTP ${response.status}`;
        throw new Error(`AIREX tool call failed for ${path}: ${detail}`);
    }

    return parsedBody;
}

function buildTextResult(result: unknown) {
    return {
        content: [
            {
                type: "text" as const,
                text: JSON.stringify(result, null, 2),
            },
        ],
    };
}

function registerReadOnlyTool(
    api: PluginApi,
    tool: Omit<ToolRegistration, "execute"> & { path: string },
) {
    api.registerTool({
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters,
        async execute(_id, params) {
            const result = await callAirex(tool.path, params);
            return buildTextResult(result);
        },
    });
}

const incidentMetaSchema: JsonSchema = {
    type: "object",
    additionalProperties: true,
};

const tenantRequestSchema: JsonSchema = {
    type: "object",
    additionalProperties: false,
    required: ["tenant_id", "incident_meta"],
    properties: {
        tenant_id: { type: "string", description: "AIREX tenant UUID" },
        incident_meta: incidentMetaSchema,
    },
};

const incidentContextSchema: JsonSchema = {
    type: "object",
    additionalProperties: false,
    required: ["tenant_id", "incident_id"],
    properties: {
        tenant_id: { type: "string", description: "AIREX tenant UUID" },
        incident_id: { type: "string", description: "AIREX incident UUID" },
    },
};

const evidenceContractSchema: JsonSchema = {
    type: "object",
    additionalProperties: false,
    required: ["tenant_id", "incident_id", "evidence"],
    properties: {
        tenant_id: { type: "string", description: "AIREX tenant UUID" },
        incident_id: { type: "string", description: "AIREX incident UUID" },
        evidence: {
            type: "object",
            additionalProperties: false,
            required: [
                "summary",
                "signals",
                "root_cause",
                "affected_entities",
                "confidence",
            ],
            properties: {
                summary: { type: "string" },
                signals: { type: "array", items: { type: "string" } },
                root_cause: { type: "string" },
                affected_entities: { type: "array", items: { type: "string" } },
                confidence: { type: "number", minimum: 0, maximum: 1 },
                raw_refs: { type: "object", additionalProperties: true },
            },
        },
    },
};

const hostDiagnosticsSchema: JsonSchema = {
    type: "object",
    additionalProperties: false,
    required: ["tenant_id", "alert_type", "incident_meta"],
    properties: {
        tenant_id: { type: "string", description: "AIREX tenant UUID" },
        alert_type: { type: "string", description: "Normalized AIREX alert type" },
        cloud: {
            type: "string",
            enum: ["aws", "gcp"],
            description: "Cloud provider when the target is a cloud host",
        },
        instance_id: { type: "string", description: "Cloud instance identifier" },
        private_ip: { type: "string", description: "Private IP of the target host" },
        incident_meta: incidentMetaSchema,
    },
};

const plugin = {
    id: "airex-tools",
    name: "AIREX Investigation Tools",
    description: "Forensic and incident-context tools backed by AIREX internal APIs",
    register(api: PluginApi) {
        registerReadOnlyTool(api, {
            name: "run_host_diagnostics",
            path: "run_host_diagnostics",
            description:
                "Run read-only host or cloud diagnostics for a target incident and return structured probe results.",
            parameters: hostDiagnosticsSchema,
        });

        registerReadOnlyTool(api, {
            name: "fetch_log_analysis",
            path: "fetch_log_analysis",
            description:
                "Analyze recent system or application logs for grouped patterns, critical lines, and spike windows.",
            parameters: tenantRequestSchema,
        });

        registerReadOnlyTool(api, {
            name: "fetch_change_context",
            path: "fetch_change_context",
            description:
                "Inspect recent infrastructure or deployment changes that may correlate with the incident.",
            parameters: tenantRequestSchema,
        });

        registerReadOnlyTool(api, {
            name: "fetch_infra_state",
            path: "fetch_infra_state",
            description:
                "Inspect scaling group, instance health, and flow-log state for the affected infrastructure.",
            parameters: tenantRequestSchema,
        });

        registerReadOnlyTool(api, {
            name: "fetch_k8s_status",
            path: "fetch_k8s_status",
            description:
                "Inspect Kubernetes pod, deployment, restart, and rollout-style status for the affected workload.",
            parameters: tenantRequestSchema,
        });

        registerReadOnlyTool(api, {
            name: "read_incident_context",
            path: "read_incident_context",
            description:
                "Read normalized incident metadata, similar incidents, pattern context, and KG context for an AIREX incident.",
            parameters: incidentContextSchema,
        });

        registerReadOnlyTool(api, {
            name: "write_evidence_contract",
            path: "write_evidence_contract",
            description:
                "Persist a normalized OpenClaw evidence contract back onto an AIREX incident.",
            parameters: evidenceContractSchema,
        });
    },
};

export default plugin;
