from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy

# Instância SQLAlchemy para compartilhar com main.py
db = SQLAlchemy()

class UserInputs(db.Model):
    """
    Modelo para armazenar os inputs do usuário entre sessões.
    """
    id = db.Column(db.Integer, primary_key=True)
    linkedin_urls = db.Column(db.Text, nullable=True)  # URLs para processamento
    ignore_urls = db.Column(db.Text, nullable=True)    # URLs para ignorar
    batch_size = db.Column(db.Integer, default=50)     # Tamanho do lote
    analyze_jobs = db.Column(db.Boolean, default=False) # Flag para análise com Gemini
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_latest():
        """
        Retorna a entrada mais recente ou cria uma nova se não existir.
        """
        instance = UserInputs.query.order_by(UserInputs.updated_at.desc()).first()
        if not instance:
            instance = UserInputs()
            db.session.add(instance)
            db.session.commit()
        return instance
    
    def update(self, linkedin_urls=None, ignore_urls=None, batch_size=None, analyze_jobs=None):
        """
        Atualiza os campos com novos valores, se fornecidos.
        """
        if linkedin_urls is not None:
            self.linkedin_urls = linkedin_urls
        if ignore_urls is not None:
            self.ignore_urls = ignore_urls
        if batch_size is not None:
            self.batch_size = batch_size
        if analyze_jobs is not None:
            self.analyze_jobs = analyze_jobs
        
        self.updated_at = datetime.utcnow()
        db.session.commit()

class ProcessedBatch(db.Model):
    """
    Modelo para armazenar informações de lotes de URLs processados.
    """
    id = db.Column(db.Integer, primary_key=True)
    batch_index = db.Column(db.Integer, nullable=False)
    urls = db.Column(db.Text, nullable=False)  # Armazenado como JSON
    results_html = db.Column(db.Text, nullable=True)
    df_json = db.Column(db.Text, nullable=True)
    has_error = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """
        Converte o modelo para um dicionário.
        """
        try:
            urls_list = json.loads(self.urls) if self.urls else []
        except:
            urls_list = []
            
        return {
            'id': self.id,
            'batch_index': self.batch_index,
            'urls': urls_list,
            'results_html': self.results_html,
            'df_json': self.df_json,
            'has_error': self.has_error,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else ''
        }

class IgnoredURL(db.Model):
    """
    Modelo para armazenar URLs que devem ser ignoradas no processamento.
    """
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)