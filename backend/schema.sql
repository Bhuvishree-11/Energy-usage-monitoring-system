-- ================================================================
--  SmartWatt – MySQL Schema  (FIXED)
-- ================================================================

CREATE DATABASE IF NOT EXISTS `energy-monitoring-system` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `energy-monitoring-system`;

-- ----------------------------------------------------------------
-- 1. Users
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('admin','manager','viewer') DEFAULT 'viewer',
    avatar_url    VARCHAR(255),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email)
);

-- ----------------------------------------------------------------
-- 2. Buildings
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Buildings (
    building_id       INT AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(150) NOT NULL,
    city              VARCHAR(100) NOT NULL,
    address           VARCHAR(255),
    building_type     VARCHAR(80),
    total_floors      INT DEFAULT 1,
    construction_year YEAR,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------
-- 3. Floors
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Floors (
    floor_id     INT AUTO_INCREMENT PRIMARY KEY,
    building_id  INT NOT NULL,
    floor_number INT NOT NULL,
    label        VARCHAR(50),
    UNIQUE KEY uq_building_floor (building_id, floor_number),
    FOREIGN KEY (building_id) REFERENCES Buildings(building_id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------
-- 4. Rooms
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Rooms (
    room_id          INT AUTO_INCREMENT PRIMARY KEY,
    floor_id         INT NOT NULL,
    room_number      VARCHAR(20) NOT NULL,
    room_type        VARCHAR(80),
    area_sqft        DECIMAL(8,2),
    occupancy_status ENUM('occupied','vacant') DEFAULT 'vacant',
    FOREIGN KEY (floor_id) REFERENCES Floors(floor_id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------
-- 5. Devices
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Devices (
    device_id         INT AUTO_INCREMENT PRIMARY KEY,
    room_id           INT NOT NULL,
    name              VARCHAR(120) NOT NULL,
    device_type       ENUM('HVAC','Lighting','IT','Appliance','Elevator','Other') NOT NULL,
    power_rating_w    DECIMAL(9,2),
    status            ENUM('online','offline','faulty') DEFAULT 'online',
    installation_date DATE,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES Rooms(room_id) ON DELETE CASCADE,
    INDEX idx_room (room_id),
    INDEX idx_status (status)
);

-- ----------------------------------------------------------------
-- 6. Sensors
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Sensors (
    sensor_id       INT AUTO_INCREMENT PRIMARY KEY,
    device_id       INT NOT NULL,
    sensor_type     ENUM('Power','Temperature','Humidity','Current','Voltage') NOT NULL,
    threshold_pct   DECIMAL(5,2) DEFAULT 100.00,
    current_value   DECIMAL(10,4),
    status          ENUM('online','offline','error') DEFAULT 'online',
    last_reading_at DATETIME,
    FOREIGN KEY (device_id) REFERENCES Devices(device_id) ON DELETE CASCADE,
    INDEX idx_device (device_id)
);

-- ----------------------------------------------------------------
-- 7. Energy_Usage
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Energy_Usage (
    usage_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id  INT NOT NULL,
    sensor_id  INT,
    timestamp  DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    energy_kwh DECIMAL(12,6) NOT NULL,
    voltage_v  DECIMAL(7,2),
    current_a  DECIMAL(7,3),
    power_kw   DECIMAL(10,4),
    cost_inr   DECIMAL(10,4),
    FOREIGN KEY (device_id) REFERENCES Devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (sensor_id) REFERENCES Sensors(sensor_id) ON DELETE SET NULL,
    INDEX idx_device_ts (device_id, timestamp),
    INDEX idx_timestamp (timestamp)
);

-- ----------------------------------------------------------------
-- 8. Alerts
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Alerts (
    alert_id        INT AUTO_INCREMENT PRIMARY KEY,
    device_id       INT NOT NULL,
    sensor_id       INT,
    severity        ENUM('critical','warning','info') DEFAULT 'warning',
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    threshold_value DECIMAL(10,4),
    actual_value    DECIMAL(10,4),
    status          ENUM('active','resolved','dismissed') DEFAULT 'active',
    triggered_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME,
    resolved_by     INT,
    FOREIGN KEY (device_id) REFERENCES Devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (sensor_id) REFERENCES Sensors(sensor_id) ON DELETE SET NULL,
    FOREIGN KEY (resolved_by) REFERENCES Users(user_id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_severity (severity)
);

-- ----------------------------------------------------------------
-- 9. Energy_Reports
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Energy_Reports (
    report_id      INT AUTO_INCREMENT PRIMARY KEY,
    building_id    INT NOT NULL,
    report_date    DATE NOT NULL,
    total_kwh      DECIMAL(14,4) NOT NULL DEFAULT 0,
    peak_kw        DECIMAL(10,4),
    peak_at        DATETIME,
    total_cost_inr DECIMAL(12,2),
    carbon_kg      DECIMAL(12,4),
    renewable_pct  DECIMAL(5,2) DEFAULT 0,
    efficiency_pct DECIMAL(5,2),
    UNIQUE KEY uq_building_date (building_id, report_date),
    FOREIGN KEY (building_id) REFERENCES Buildings(building_id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------
-- 10. Settings
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Settings (
    setting_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT,
    setting_key   VARCHAR(100) NOT NULL,
    setting_value TEXT,
    UNIQUE KEY uq_user_key (user_id, setting_key),
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- ================================================================
--  SEED DATA
-- ================================================================

-- Users (SHA-256 hash of "admin123")
INSERT INTO Users (name, email, password_hash, role) VALUES
('System Administrator', 'admin@smartwatt.com',   '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'admin'),
('Building Manager',     'manager@smartwatt.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'manager'),
('Facility Viewer',      'viewer@smartwatt.com',  '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'viewer')
ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash);

-- Buildings
INSERT INTO Buildings (name, city, address, building_type, total_floors, construction_year) VALUES
('Tech Park Alpha',    'Bengaluru', 'Whitefield, Bengaluru 560066',    'Commercial IT Park', 5, 2015),
('Cyber Hub',          'Gurugram',  'DLF Cyber City, Gurugram 122002', 'Commercial Office',  8, 2012),
('Mindspace',          'Hyderabad', 'Madhapur, Hyderabad 500081',      'IT SEZ',             6, 2016),
('Prestige Tech Park', 'Bengaluru', 'Sarjapur Road, Bengaluru 560103', 'Commercial IT Park', 7, 2018);

-- Floors
INSERT INTO Floors (building_id, floor_number, label) VALUES
(1,1,'Ground'),(1,2,'First'),(1,3,'Second'),
(2,1,'Ground'),(2,2,'First'),(2,3,'Second'),
(3,1,'Ground'),(3,2,'First'),(3,3,'Second'),
(4,1,'Ground'),(4,2,'First'),(4,3,'Second');

-- Rooms
INSERT INTO Rooms (floor_id, room_number, room_type, area_sqft, occupancy_status) VALUES
(1,'101','Server Room',       400,'occupied'),
(1,'102','Open Office',       800,'occupied'),
(1,'103','Conference Room',   300,'occupied'),
(1,'104','Reception',         200,'occupied'),
(2,'201','Open Office',       800,'occupied'),
(2,'202','Manager Cabin',     250,'occupied'),
(2,'203','Training Room',     500,'vacant'),
(2,'204','Pantry',            150,'occupied'),
(4,'101','Trading Floor',    1200,'occupied'),
(4,'102','IT Infrastructure', 600,'occupied'),
(4,'103','Board Room',        400,'occupied'),
(7,'101','Development Lab',   700,'occupied'),
(7,'102','QA Lab',            400,'occupied'),
(7,'103','Cafeteria',         500,'occupied');

-- Devices
INSERT INTO Devices (room_id, name, device_type, power_rating_w, status, installation_date) VALUES
(1, 'Main Server HVAC',    'HVAC',      3500, 'online',  '2020-01-15'),
(1, 'Server Rack Cooling', 'HVAC',      2800, 'online',  '2020-01-15'),
(1, 'Server Rack Lights',  'Lighting',   180, 'online',  '2020-01-15'),
(2, 'Office HVAC A',       'HVAC',      2000, 'online',  '2020-03-10'),
(2, 'Lighting Zone A',     'Lighting',   600, 'online',  '2020-03-10'),
(2, 'Lighting Zone B',     'Lighting',   600, 'online',  '2020-03-10'),
(2, 'Workstation Cluster', 'IT',        1800, 'online',  '2021-06-01'),
(3, 'Conference HVAC',     'HVAC',      1500, 'online',  '2020-03-10'),
(3, 'AV System',           'Appliance',  800, 'offline', '2020-03-10'),
(3, 'Conference Lights',   'Lighting',   240, 'online',  '2020-03-10'),
(5, 'Office HVAC B',       'HVAC',      2000, 'online',  '2020-04-01'),
(5, 'Lighting Zone C',     'Lighting',   600, 'faulty',  '2020-04-01'),
(6, 'Exec HVAC',           'HVAC',      1200, 'online',  '2020-04-01'),
(9, 'Trading HVAC 1',      'HVAC',      4000, 'online',  '2019-05-20'),
(9, 'Trading HVAC 2',      'HVAC',      4000, 'online',  '2019-05-20'),
(9, 'UPS System',          'IT',        5000, 'online',  '2019-05-20'),
(10,'IT Room HVAC',        'HVAC',      3000, 'online',  '2019-05-20');

-- Sensors
INSERT INTO Sensors (device_id, sensor_type, threshold_pct, current_value, status) VALUES
(1,  'Power',       80,   2800, 'online'),
(1,  'Temperature', 85,     42, 'online'),
(2,  'Power',       80,   2200, 'online'),
(4,  'Power',       90,   1800, 'online'),
(4,  'Current',     85,    8.2, 'online'),
(5,  'Power',       75,    450, 'online'),
(7,  'Power',       90,   1650, 'online'),
(9,  'Power',       80,   3200, 'online'),
(14, 'Power',       80,   3800, 'online'),
(15, 'Power',       75,   3000, 'online'),
(16, 'Power',       85,   4500, 'online'),
(12, 'Power',       NULL, NULL, 'error');

-- ================================================================
-- REALISTIC ENERGY USAGE DATA
-- ================================================================

INSERT INTO Energy_Usage
(device_id, sensor_id, timestamp, energy_kwh, voltage_v, current_a, power_kw, cost_inr)
VALUES

-- JANUARY
(1,1,'2025-01-05 09:00:00',15.2,229,14.2,3.5,103.06),
(1,1,'2025-01-10 09:00:00',16.1,231,14.8,3.7,109.16),
(4,4,'2025-01-12 10:00:00',12.8,230,10.9,2.8,86.78),
(7,7,'2025-01-15 11:00:00',18.4,232,15.3,4.0,124.75),
(14,9,'2025-01-20 12:00:00',25.6,228,17.8,5.2,173.57),

-- FEBRUARY
(1,1,'2025-02-05 09:00:00',14.5,230,13.8,3.3,98.31),
(4,4,'2025-02-08 10:00:00',11.9,231,10.1,2.6,80.68),
(7,7,'2025-02-15 11:00:00',17.2,229,14.7,3.8,116.62),
(14,9,'2025-02-18 12:00:00',24.8,227,17.4,5.0,168.14),

-- MARCH
(1,1,'2025-03-05 09:00:00',13.8,229,13.2,3.1,93.56),
(4,4,'2025-03-10 10:00:00',11.1,232,9.8,2.5,75.26),
(7,7,'2025-03-14 11:00:00',16.3,231,14.0,3.6,110.51),
(14,9,'2025-03-21 12:00:00',23.5,229,16.9,4.8,159.33),

-- APRIL
(1,1,'2025-04-03 09:00:00',13.2,230,12.8,3.0,89.50),
(4,4,'2025-04-08 10:00:00',10.6,229,9.5,2.3,71.87),
(7,7,'2025-04-16 11:00:00',15.4,230,13.7,3.4,104.41),
(14,9,'2025-04-22 12:00:00',22.8,230,16.2,4.6,154.58),

-- MAY
(1,1,'2025-05-04 09:00:00',12.6,231,12.1,2.9,85.43),
(4,4,'2025-05-09 10:00:00',10.1,230,9.1,2.2,68.48),
(7,7,'2025-05-14 11:00:00',14.8,229,13.2,3.2,100.34),
(14,9,'2025-05-20 12:00:00',21.5,228,15.5,4.3,145.77),

-- JUNE
(1,1,'2025-06-05 09:00:00',11.8,229,11.5,2.7,80.00),
(4,4,'2025-06-10 10:00:00',9.4,230,8.5,2.0,63.73),
(7,7,'2025-06-15 11:00:00',13.7,231,12.4,3.0,92.89),
(14,9,'2025-06-18 12:00:00',19.8,229,14.1,4.0,134.24);

-- Alerts
INSERT INTO Alerts (device_id, sensor_id, severity, title, description, threshold_value, actual_value, status) VALUES
(1,  1,    'critical', 'Critical Overload: Main Server HVAC',  'Current drawn (58A) exceeds safe threshold (50A) in Tech Park Alpha - Server Room.', 50.00, 58.00, 'active'),
(6,  NULL, 'warning',  'Unusual Idle Consumption',             'Lighting Zone B (Cyber Hub) is active during scheduled offline hours.',               0.00,  0.60,  'active'),
(11, NULL, 'info',     'Sensor Disconnected',                  'Temperature Sensor T-402 connection restored.',                                        NULL,  NULL,  'resolved');

INSERT INTO Energy_Reports
(building_id, report_date, total_kwh, peak_kw, total_cost_inr, carbon_kg, renewable_pct, efficiency_pct)
VALUES
(1,'2025-01-31',24800,185,168144,11408,8,72),
(1,'2025-02-28',23500,178,159330,10810,9,74),
(1,'2025-03-31',22100,170,149838,10166,10,78),
(1,'2025-04-30',21800,168,147804,10028,11,80),
(1,'2025-05-31',20500,160,138990,9430,11,82),
(1,'2025-06-30',19400,152,131532,8924,12,85);

-- Settings
INSERT INTO Settings (user_id, setting_key, setting_value) VALUES
(NULL, 'global_power_threshold_kw', '150'),
(NULL, 'cost_per_kwh_inr',          '6.78'),
(NULL, 'carbon_factor_kg_per_kwh',  '0.46'),
(NULL, 'alert_email_enabled',       'true'),
(NULL, 'alert_sms_enabled',         'true'),
(NULL, 'auto_reports_enabled',      'false'),
(1,    'email_notifications',       'true'),
(1,    'sms_critical_alerts',       'true')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);