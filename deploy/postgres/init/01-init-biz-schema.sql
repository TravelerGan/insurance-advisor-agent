CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    clause_name VARCHAR(300) NOT NULL,
    category VARCHAR(50) NOT NULL,
    insurer VARCHAR(120) NOT NULL,
    image_url TEXT,
    description TEXT,
    min_premium DECIMAL(14,2),
    max_premium DECIMAL(14,2),
    target_group VARCHAR(300),
    highlights TEXT[],
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_products_category CHECK (category IN ('medical', 'critical_illness', 'accident', 'life'))
);

-- Fictional product used for the local portfolio demo.
INSERT INTO products (name, clause_name, category, insurer, description, target_group, highlights, min_premium, image_url)
VALUES ('示例住院医疗险', 'sample-medical-policy.md', 'medical', '虚构示例保险公司',
        '演示产品。详情以仓库内的虚构条款为准。', '演示用户', ARRAY['住院费用', '30 天等待期'], 120, '');

-- Placeholder used by the frontend's local demo session.
INSERT INTO users (username, email, password_hash, display_name)
VALUES ('demo', 'demo@example.test', 'disabled-demo-login', '演示用户');

CREATE TABLE IF NOT EXISTS insurance_plans (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    plan_name VARCHAR(120) NOT NULL,
    summary TEXT,
    insured_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    annual_premium_budget DECIMAL(14, 2),
    status VARCHAR(30) NOT NULL DEFAULT 'uninsured',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_insurance_plans_budget
        CHECK (annual_premium_budget IS NULL OR annual_premium_budget >= 0),
    CONSTRAINT chk_insurance_plans_status
        CHECK (status IN ('uninsured', 'applying', 'insured'))
);

CREATE TABLE IF NOT EXISTS insurance_plan_items (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES insurance_plans(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id),
    priority INT NOT NULL DEFAULT 1 CHECK (priority >= 1),
    recommendation_reason TEXT,
    annual_premium_budget DECIMAL(14, 2),
    status VARCHAR(30) NOT NULL DEFAULT 'uninsured',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_insurance_plan_items_budget
        CHECK (annual_premium_budget IS NULL OR annual_premium_budget >= 0),
    CONSTRAINT chk_insurance_plan_items_status
        CHECK (status IN ('uninsured', 'insured')),
    CONSTRAINT uk_insurance_plan_items_plan_product
        UNIQUE (plan_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_insurance_plans_user
    ON insurance_plans(user_id, status);

CREATE INDEX IF NOT EXISTS idx_insurance_plan_items_plan
    ON insurance_plan_items(plan_id, status);
