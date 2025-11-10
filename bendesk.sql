Create Database bendesk_dev;
Use bendesk_dev;

select * from users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(50) NOT NULL,
    profile VARCHAR(20) NOT NULL, -- exemplo: 'Administrador', 'Suporte', 'Usuário'
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    email VARCHAR(100)
);

INSERT INTO users (username, password, profile, first_name, last_name, email)
VALUES ('admin', 'admin', 'Administrador', 'Admin', 'Master', 'admin@bendesk.local');

CREATE TABLE tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status ENUM('Aberto', 'Em Andamento', 'Encerrado', 'Cancelado') DEFAULT 'Aberto',
    priority ENUM('Baixa', 'Média', 'Alta') DEFAULT 'Média',
    requester_email VARCHAR(150),
    requester_name VARCHAR(100),
    assigned_to VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ========================
-- HISTÓRICO DE ALTERAÇÕES
-- ========================
CREATE TABLE ticket_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    changed_by VARCHAR(100),
    change_description TEXT,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

-- ========================
-- COMENTÁRIOS
-- ========================
CREATE TABLE ticket_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    commenter VARCHAR(100),
    comment TEXT,
    commented_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

-- ========================
-- ANEXOS
-- ========================
CREATE TABLE ticket_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    filename VARCHAR(255),
    filepath VARCHAR(255),
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
);

CREATE TABLE cost_centers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20),
    name VARCHAR(100)
);

CREATE TABLE device_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(100),
    department VARCHAR(100),
    cost_center_id INT
);

CREATE TABLE asset_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100)
);

CREATE TABLE estoque_itens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    categoria VARCHAR(50),
    quantidade FLOAT DEFAULT 0,
    unidade VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE estoque_movimentacoes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo VARCHAR(20),
    item_id INT NOT NULL,
    quantidade FLOAT,
    descricao VARCHAR(255),
    usuario VARCHAR(100),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES estoque_itens(id) ON DELETE CASCADE
);

CREATE TABLE assets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_type VARCHAR(100) NOT NULL,
    type_id INT,
    brand VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100) UNIQUE,
    hostname VARCHAR(100),
    invoice_number VARCHAR(100),
    patrimony_code VARCHAR(100),
    status VARCHAR(50),
    ownership VARCHAR(50),
    location VARCHAR(100),
    cost_center_id INT,
    device_user_id INT,
    acquisition_date DATE,
    return_date DATE,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (type_id) REFERENCES asset_types(id),
    FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id),
    FOREIGN KEY (device_user_id) REFERENCES device_users(id)
);

ALTER TABLE cost_centers 
ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;


-- ==============================
-- ✅ DEVICE_USERS
-- ==============================
ALTER TABLE device_users
ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- ==============================
-- ✅ ASSETS
-- (já tem created_at e updated_at, apenas garantido)
-- ==============================
-- ERRO--
ALTER TABLE assets
MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
MODIFY COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ==============================
-- ✅ ASSET_TYPES
-- ==============================
-- (sem alterações — o models.py não usa timestamps aqui)

-- ==============================
-- ✅ ESTOQUE_ITENS
-- ==============================
ALTER TABLE estoque_itens
MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- ==============================
-- ✅ ESTOQUE_MOVIMENTACOES
-- ==============================
ALTER TABLE estoque_movimentacoes
MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;

-- ==============================
-- ✅ USERS
-- (garantindo compatibilidade total)
-- ==============================
ALTER TABLE users
MODIFY COLUMN is_active BOOLEAN DEFAULT TRUE,
MODIFY COLUMN email VARCHAR(100) NULL;

-- ==============================
-- ✅ TICKETS
-- (já com timestamps corretos)
-- ==============================
ALTER TABLE tickets
MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
MODIFY COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ==============================
-- ✅ TICKET_HISTORY
-- ==============================
ALTER TABLE ticket_history
MODIFY COLUMN changed_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- ==============================
-- ✅ TICKET_COMMENTS
-- ==============================
ALTER TABLE ticket_comments
MODIFY COLUMN commented_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- ==============================
-- ✅ TICKET_ATTACHMENTS
-- ==============================
ALTER TABLE ticket_attachments
MODIFY COLUMN uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP;

SHOW TABLES;
