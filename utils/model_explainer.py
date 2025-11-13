import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.inspection import permutation_importance
import joblib
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("⚠️ SHAP not available. Install with: pip install shap")

class ModelExplainer:
    """Advanced model explainability untuk trading ML models"""
    
    def __init__(self, model_path="models/trading_model.pkl", feature_names=None):
        self.model_path = model_path
        self.model = None
        self.feature_names = feature_names or [
            'rsi', 'macd', 'sma_20', 'sma_50', 'ema_12', 'ema_26',
            'atr', 'volume_ratio', 'price_change_1d', 'price_change_5d',
            'volatility', 'momentum', 'williams_r', 'cci', 'obv'
        ]
        self.load_model()
        
    def load_model(self):
        """Load model dari file"""
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                print("✅ Model loaded successfully for explainability")
                return True
            else:
                print("❌ Model file not found")
                return False
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            return False
    
    def explain_prediction(self, features_df, instance_index=0):
        """Explain individual prediction dengan feature contributions"""
        if self.model is None:
            return {"error": "Model not loaded"}
            
        try:
            # Convert to numpy array jika perlu
            if isinstance(features_df, pd.DataFrame):
                features_array = features_df.values
            else:
                features_array = features_df
                
            # Pastikan bentuk features benar
            if len(features_array.shape) == 1:
                features_array = features_array.reshape(1, -1)
                
            # Get prediction probabilities
            probabilities = self.model.predict_proba(features_array)[instance_index]
            prediction = self.model.predict(features_array)[instance_index]
            
            explanation = {
                'prediction': int(prediction),
                'probabilities': {
                    'DOWN': float(probabilities[0]),
                    'NEUTRAL': float(probabilities[1]) if len(probabilities) > 2 else 0.0,
                    'UP': float(probabilities[-1])
                },
                'confidence': float(np.max(probabilities)),
                'feature_contributions': {}
            }
            
            # SHAP explanation jika tersedia
            if SHAP_AVAILABLE and hasattr(self.model, 'predict_proba'):
                explainer = shap.TreeExplainer(self.model)
                shap_values = explainer.shap_values(features_array)
                
                # Handle multi-class SHAP values
                if isinstance(shap_values, list):
                    # Use the class dengan probability tertinggi
                    pred_class = np.argmax(probabilities)
                    instance_shap = shap_values[pred_class][instance_index]
                else:
                    instance_shap = shap_values[instance_index]
                
                # Map SHAP values ke feature names
                for i, feature_name in enumerate(self.feature_names):
                    if i < len(instance_shap):
                        explanation['feature_contributions'][feature_name] = {
                            'shap_value': float(instance_shap[i]),
                            'abs_impact': abs(float(instance_shap[i])),
                            'feature_value': float(features_array[instance_index][i])
                        }
                
                # Sort by absolute impact
                explanation['feature_contributions'] = dict(
                    sorted(explanation['feature_contributions'].items(), 
                          key=lambda x: x[1]['abs_impact'], reverse=True)
                )
            
            return explanation
            
        except Exception as e:
            return {"error": f"Explanation failed: {str(e)}"}
    
    def generate_feature_importance(self, X, y, method='permutation'):
        """Generate comprehensive feature importance analysis"""
        if self.model is None:
            return {"error": "Model not loaded"}
            
        try:
            if method == 'permutation':
                # Permutation importance
                perm_importance = permutation_importance(
                    self.model, X, y, n_repeats=10, random_state=42
                )
                
                importance_df = pd.DataFrame({
                    'feature': self.feature_names[:len(perm_importance.importances_mean)],
                    'importance_mean': perm_importance.importances_mean,
                    'importance_std': perm_importance.importances_std
                }).sort_values('importance_mean', ascending=False)
                
            else:
                # Model-builtin importance
                if hasattr(self.model, 'feature_importances_'):
                    importance_df = pd.DataFrame({
                        'feature': self.feature_names[:len(self.model.feature_importances_)],
                        'importance_mean': self.model.feature_importances_,
                        'importance_std': np.zeros(len(self.model.feature_importances_))
                    }).sort_values('importance_mean', ascending=False)
                else:
                    return {"error": "Model doesn't have feature_importances_"}
            
            return {
                'feature_importance': importance_df.to_dict('records'),
                'top_features': importance_df.head(10)['feature'].tolist(),
                'least_important': importance_df.tail(5)['feature'].tolist()
            }
            
        except Exception as e:
            return {"error": f"Feature importance failed: {str(e)}"}
    
    def model_performance_report(self, X_test, y_test):
        """Generate comprehensive model performance report"""
        if self.model is None:
            return {"error": "Model not loaded"}
            
        try:
            from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
            
            predictions = self.model.predict(X_test)
            probabilities = self.model.predict_proba(X_test)
            
            # Basic metrics
            accuracy = accuracy_score(y_test, predictions)
            class_report = classification_report(y_test, predictions, output_dict=True)
            conf_matrix = confusion_matrix(y_test, predictions).tolist()
            
            # Confidence analysis
            max_probs = np.max(probabilities, axis=1)
            confidence_stats = {
                'mean_confidence': float(np.mean(max_probs)),
                'std_confidence': float(np.std(max_probs)),
                'high_confidence_rate': float(np.sum(max_probs > 0.7) / len(max_probs)),
                'low_confidence_rate': float(np.sum(max_probs < 0.5) / len(max_probs))
            }
            
            # Class distribution
            unique, counts = np.unique(predictions, return_counts=True)
            class_distribution = dict(zip(unique.astype(str), counts.tolist()))
            
            return {
                'accuracy': accuracy,
                'classification_report': class_report,
                'confusion_matrix': conf_matrix,
                'confidence_analysis': confidence_stats,
                'class_distribution': class_distribution,
                'test_set_size': len(X_test),
                'feature_count': X_test.shape[1]
            }
            
        except Exception as e:
            return {"error": f"Performance report failed: {str(e)}"}
    
    def generate_trading_insights(self, feature_analysis, market_conditions):
        """Generate trading-specific insights dari model analysis"""
        insights = {
            'key_drivers': [],
            'risk_factors': [],
            'market_regime_adaption': [],
            'recommendations': []
        }
        
        # Analyze feature importance untuk trading insights
        for feature in feature_analysis.get('feature_importance', [])[:5]:
            feature_name = feature['feature']
            importance = feature['importance_mean']
            
            # Trading-specific interpretations
            if feature_name in ['rsi', 'williams_r'] and importance > 0.1:
                insights['key_drivers'].append(
                    f"Momentum indicators ({feature_name}) are strong predictors"
                )
            elif feature_name in ['atr', 'volatility'] and importance > 0.08:
                insights['risk_factors'].append(
                    f"Volatility measures ({feature_name}) significantly impact predictions"
                )
            elif feature_name in ['volume_ratio', 'obv'] and importance > 0.05:
                insights['key_drivers'].append(
                    f"Volume analysis ({feature_name}) provides important signals"
                )
        
        # Market regime insights
        if market_conditions.get('volatility', 0) > 0.03:
            insights['market_regime_adaption'].append(
                "High volatility regime - model may rely more on risk management features"
            )
        else:
            insights['market_regime_adaption'].append(
                "Low volatility regime - trend and momentum features likely more important"
            )
        
        # Recommendations
        if len(insights['key_drivers']) > 0:
            insights['recommendations'].append(
                "Focus on validating the key driving features in current market conditions"
            )
        
        if len(insights['risk_factors']) > 0:
            insights['recommendations'].append(
                "Monitor risk factors closely as they significantly influence model decisions"
            )
        
        return insights
    
    def create_explanation_dashboard(self, X, y, output_path="model_explanation.html"):
        """Create comprehensive explanation dashboard"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # Create visualization
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # 1. Feature Importance
            feature_importance = self.generate_feature_importance(X, y)
            if 'feature_importance' in feature_importance:
                fi_df = pd.DataFrame(feature_importance['feature_importance'])
                sns.barplot(data=fi_df.head(10), x='importance_mean', y='feature', ax=axes[0,0])
                axes[0,0].set_title('Top 10 Feature Importance')
            
            # 2. Performance Metrics
            performance = self.model_performance_report(X, y)
            if 'accuracy' in performance:
                metrics_data = {
                    'Metric': ['Accuracy', 'High Confidence Rate', 'Low Confidence Rate'],
                    'Value': [
                        performance['accuracy'],
                        performance['confidence_analysis']['high_confidence_rate'],
                        performance['confidence_analysis']['low_confidence_rate']
                    ]
                }
                metrics_df = pd.DataFrame(metrics_data)
                sns.barplot(data=metrics_df, x='Value', y='Metric', ax=axes[0,1])
                axes[0,1].set_title('Model Performance Metrics')
            
            # 3. Confidence Distribution
            if SHAP_AVAILABLE:
                explainer = shap.TreeExplainer(self.model)
                shap_values = explainer.shap_values(X)
                shap.summary_plot(shap_values, X, feature_names=self.feature_names, show=False, ax=axes[1,0])
                axes[1,0].set_title('SHAP Feature Impact')
            
            # 4. Class Distribution
            if 'class_distribution' in performance:
                class_df = pd.DataFrame(list(performance['class_distribution'].items()), 
                                      columns=['Class', 'Count'])
                sns.barplot(data=class_df, x='Class', y='Count', ax=axes[1,1])
                axes[1,1].set_title('Prediction Class Distribution')
            
            plt.tight_layout()
            plt.savefig(output_path.replace('.html', '.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
            # Create HTML report
            self._create_html_report(feature_importance, performance, output_path)
            
            return {"success": True, "dashboard_path": output_path}
            
        except Exception as e:
            return {"error": f"Dashboard creation failed: {str(e)}"}
    
    def _create_html_report(self, feature_importance, performance, output_path):
        """Create HTML report untuk model explanation"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trading Model Explanation Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                .feature {{ margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 3px; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #e9ecef; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>🤖 Trading Model Explanation Dashboard</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="section">
                <h2>📊 Model Performance</h2>
                <div class="metric">Accuracy: {performance.get('accuracy', 0):.3f}</div>
                <div class="metric">Test Samples: {performance.get('test_set_size', 0)}</div>
                <div class="metric">Features: {performance.get('feature_count', 0)}</div>
            </div>
            
            <div class="section">
                <h2>🎯 Feature Importance</h2>
        """
        
        # Add feature importance
        for feature in feature_importance.get('feature_importance', [])[:10]:
            html_content += f"""
                <div class="feature">
                    <strong>{feature['feature']}</strong>: {feature['importance_mean']:.4f} ± {feature['importance_std']:.4f}
                </div>
            """
        
        html_content += """
            </div>
            
            <div class="section">
                <h2>📈 Visualization</h2>
                <img src="model_explanation.png" alt="Model Explanation Charts" style="max-width: 100%;">
            </div>
            
            <div class="section">
                <h2>💡 Trading Insights</h2>
                <ul>
        """
        
        # Add trading insights
        insights = self.generate_trading_insights(feature_importance, {})
        for category, items in insights.items():
            if items:
                html_content += f"<li><strong>{category.replace('_', ' ').title()}:</strong><ul>"
                for item in items:
                    html_content += f"<li>{item}</li>"
                html_content += "</ul></li>"
        
        html_content += """
                </ul>
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html_content)
