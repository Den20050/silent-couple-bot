-- ============================================================================
-- Silent Couple Bot 2.2 — Complete Database Schema (Dual Mode)
-- ============================================================================

-- ========================================
-- USERS — Core user data (GDPR compliant)
-- ========================================
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    tg_username TEXT,
    utc_offset SMALLINT DEFAULT 3,
    next_send_at TIMESTAMPTZ,
    consent BOOLEAN DEFAULT FALSE,
    consent_dt TIMESTAMPTZ,
    consent_ip INET,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT tg_id_positive CHECK (tg_id > 0)
);

COMMENT ON TABLE users IS 'Core user data, minimized for GDPR';
COMMENT ON COLUMN users.consent_ip IS 'Stored for 152-FZ compliance, anonymized after 90d';

-- ========================================
-- PAIRS — Relationship between two users
-- ========================================
CREATE TABLE pairs (
    id BIGSERIAL PRIMARY KEY,
    uid_a BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    uid_b BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'past_due', 'cancelled')),
    trial_end DATE,
    mode TEXT DEFAULT 'silent' CHECK (mode IN ('silent', 'chat')), -- DUAL MODE FIELD
    common_chat_id BIGINT, -- Telegram group/chat ID for mode='chat'
    morning_initiator_uid BIGINT REFERENCES users(id),
    morning_message_id_a INTEGER,
    morning_message_id_b INTEGER,
    evening_initiator_uid BIGINT REFERENCES users(id),
    evening_message_id_a INTEGER,
    evening_message_id_b INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(uid_a, uid_b),
    CHECK (uid_a < uid_b) -- Prevent duplicate pairs (A,B) and (B,A)
);

CREATE INDEX idx_pairs_status_mode ON pairs(status, mode); -- For W3/W4 filtering
CREATE INDEX idx_pairs_common_chat ON pairs(common_chat_id) WHERE common_chat_id IS NOT NULL;
COMMENT ON TABLE pairs IS 'Pair relationships with dual mode support';
COMMENT ON COLUMN pairs.mode IS 'silent: isolated bot chat, chat: integrated into personal chat';

-- ========================================
-- SUBSCRIPTIONS — Payment tracking
-- ========================================
CREATE TABLE subscriptions (
    id BIGSERIAL PRIMARY KEY,
    pair_id BIGINT NOT NULL REFERENCES pairs(id) ON DELETE CASCADE,
    payer_uid BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    external_id TEXT UNIQUE, -- YooKassa payment ID
    status TEXT DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'past_due', 'cancelled', 'refunded')),
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_subs_period_end ON subscriptions(current_period_end, status) WHERE status IN ('trial', 'active', 'past_due');
CREATE INDEX idx_subs_payer ON subscriptions(payer_uid);

-- ========================================
-- PINGS — Interaction logs (partitioned)
-- ========================================
CREATE TABLE pings (
    id BIGSERIAL,
    pair_id BIGINT NOT NULL REFERENCES pairs(id) ON DELETE CASCADE,
    sender_uid BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type TEXT CHECK (type IN ('morning', 'evening', 'tap', 'request')),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, sent_at)
) PARTITION BY RANGE (sent_at);

COMMENT ON TABLE pings IS 'Partitioned by month, auto-cleanup after 90d';

-- Create partitions for next 2 years
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '2 years';
    cur_date DATE;
BEGIN
    FOR cur_date IN SELECT generate_series(start_date, end_date, '1 month')
    LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS pings_%s_%s PARTITION OF pings FOR VALUES FROM (%L) TO (%L)',
            TO_CHAR(cur_date, 'YYYY'),
            TO_CHAR(cur_date, 'MM'),
            cur_date,
            cur_date + INTERVAL '1 month'
        );
    END LOOP;
END $$;

CREATE INDEX idx_pings_pair_date ON pings(pair_id, sent_at);
CREATE INDEX idx_pings_sender ON pings(sender_uid);

-- ========================================
-- PICS_POOL — Image library
-- ========================================
CREATE TABLE pics_pool (
    file_id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('morning', 'evening')),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pool_type ON pics_pool(type);

-- ========================================
-- PIC_LEDGER — Sent image history (partitioned)
-- ========================================
CREATE TABLE pic_ledger (
    pair_id BIGINT NOT NULL,
    file_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('A', 'B')),
    sent_at DATE NOT NULL,
    PRIMARY KEY (pair_id, file_id, role, sent_at)
) PARTITION BY RANGE (sent_at);

COMMENT ON TABLE pic_ledger IS 'Ensures 30-day uniqueness per pair';

-- Auto-create partitions for 2 years
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '2 years';
    cur_date DATE;
BEGIN
    FOR cur_date IN SELECT generate_series(start_date, end_date, '1 month')
    LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS ledger_%s_%s PARTITION OF pic_ledger FOR VALUES FROM (%L) TO (%L)',
            TO_CHAR(cur_date, 'YYYY'),
            TO_CHAR(cur_date, 'MM'),
            cur_date,
            cur_date + INTERVAL '1 month'
        );
    END LOOP;
END $$;

CREATE INDEX idx_ledger_pair_date ON pic_ledger(pair_id, sent_at);

-- ========================================
-- REFUNDS — Refund log
-- ========================================
CREATE TABLE refunds (
    id BIGSERIAL PRIMARY KEY,
    sub_id BIGINT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    amount_cents INT NOT NULL CHECK (amount_cents > 0),
    reason TEXT CHECK (reason IN ('downtime', 'user_request', 'duplicate')),
    refund_id TEXT UNIQUE, -- YooKassa refund ID
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_refunds_sub ON refunds(sub_id);

-- ========================================
-- CONSENT_AUDIT — GDPR compliance
-- ========================================
CREATE TABLE consent_audit (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('accepted', 'updated', 'withdrawn')),
    ip INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_consent_user ON consent_audit(user_id);
CREATE INDEX idx_consent_created ON consent_audit(created_at);

-- ========================================
-- CIRCUIT_BREAKER — Fault tolerance
-- ========================================
CREATE TABLE circuit_breaker (
    service TEXT PRIMARY KEY CHECK (service IN ('yookassa', 'telegram', 'miniapp')),
    error_count INT DEFAULT 0,
    is_open BOOLEAN DEFAULT FALSE,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    total_failures INT DEFAULT 0,
    last_error TEXT
);

COMMENT ON TABLE circuit_breaker IS 'Tracks failures for circuit breaker pattern';

-- ========================================
-- FUNCTIONS — Helper functions
-- ========================================
CREATE OR REPLACE FUNCTION create_next_month_partitions()
RETURNS VOID AS $$
DECLARE
    next_month DATE := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    partition_name TEXT;
BEGIN
    partition_name := format('pings_%s_%s', TO_CHAR(next_month, 'YYYY'), TO_CHAR(next_month, 'MM'));
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF pings FOR VALUES FROM (%L) TO (%L)', 
        partition_name, next_month, next_month + INTERVAL '1 month');
    
    partition_name := format('ledger_%s_%s', TO_CHAR(next_month, 'YYYY'), TO_CHAR(next_month, 'MM'));
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF pic_ledger FOR VALUES FROM (%L) TO (%L)', 
        partition_name, next_month, next_month + INTERVAL '1 month');
END;
$$ LANGUAGE plpgsql;

-- Call monthly
SELECT create_next_month_partitions();

-- ========================================
-- TRIGGERS — Auto-updating timestamps
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pairs_updated_at BEFORE UPDATE ON pairs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- ROW LEVEL SECURITY (опционально, для мультиарендности)
-- ========================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE pairs ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY users_self ON users FOR SELECT USING (tg_id = current_setting('app.current_user_id')::BIGINT);