-- Автоматическое создание партиций на 1 год вперёд
DO $$
DECLARE
    start_date DATE := CURRENT_DATE;
    end_date DATE := CURRENT_DATE + INTERVAL '1 year';
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
        
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS ledger_%s_%s PARTITION OF pic_ledger FOR VALUES FROM (%L) TO (%L)',
            TO_CHAR(cur_date, 'YYYY'),
            TO_CHAR(cur_date, 'MM'),
            cur_date,
            cur_date + INTERVAL '1 month'
        );
    END LOOP;
END $$;