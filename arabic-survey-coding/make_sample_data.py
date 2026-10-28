"""Write a synthetic Arabic survey for testing the tagger.

Every answer below was written for this demo. None of it comes from a real
person or organisation. The intended themes are saved as gold labels so the
tagger can be scored against them.

    python make_sample_data.py
"""

import csv
from pathlib import Path

DATA = Path(__file__).parent / "data"

QUESTIONS = {
    "Q1": "ما هي أهم احتياجات أسرتك في الوقت الحالي؟ ولماذا؟",
    "Q2": "ما ملاحظاتك على طريقة تقديم المساعدات من المؤسسة؟ وكيف يمكن تحسينها؟",
}

# (question, site, gender, answer, gold themes, gold sentiment, gold followup)
ROWS = [
    # Q1: needs
    ("Q1", "A", "F", "أكتر إشي محتاجينه أكل للأولاد، الطحين خلص من أسبوع ومش لاقيين نشتري", "FOOD;CASH", "negative", 0),
    ("Q1", "A", "M", "الخيمة صارت مهترئة والمي بتدخل علينا لما تشتي، بدنا خيمة جديدة وشوادر", "SHELTER", "negative", 0),
    ("Q1", "B", "F", "ابني عنده سكري وما في انسولين بالعيادة القريبة، بنضطر نمشي مسافة طويلة", "HEALTH", "negative", 0),
    ("Q1", "C", "M", "نحتاج مياه صالحة للشرب، المياه الموجودة مالحة والأطفال يمرضون منها", "WASH;HEALTH", "negative", 0),
    ("Q1", "B", "F", "فوط صحية وصابون ومواد تنظيف، ما في عنا إشي من هالأغراض أبدًا", "WASH", "negative", 0),
    ("Q1", "A", "M", "بدي شغل، كنت نجار وخسرت المعدات كلها، لو في دعم لمشروع صغير برجع أشتغل", "LIVELIHOODS", "neutral", 0),
    ("Q1", "C", "F", "الأولاد صار لهم سنة بدون مدرسة، نتمنى يكون في خيمة تعليمية قريبة", "EDUCATION", "negative", 0),
    ("Q1", "B", "M", "مساعدة نقدية أفضل من الطرود لأنه كل عيلة احتياجها مختلف", "CASH", "neutral", 0),
    ("Q1", "A", "F", "ما عنا غاز للطبخ، بنحرق كرتون وبلاستيك وهذا بضر صدر الأولاد", "ENERGY;HEALTH", "negative", 0),
    ("Q1", "C", "M", "الكهرباء مقطوعة دائمًا، نحتاج لوح طاقة شمسية صغير على الأقل لشحن الجوالات والإضاءة", "ENERGY", "negative", 0),
    ("Q1", "B", "F", "بنتي صارت تخاف من أي صوت وتصحى بالليل تبكي، محتاجين حدا يساعدها نفسيًا", "MENTAL_HEALTH", "negative", 0),
    ("Q1", "A", "F", "حليب أطفال وحفاضات، عندي توأم عمرهم ثلاث شهور", "FOOD;WASH", "negative", 0),
    ("Q1", "C", "M", "أغطية وفرشات قبل الشتاء، نحن ثمانية أشخاص على ثلاث فرشات", "SHELTER", "negative", 0),
    ("Q1", "B", "M", "الحمامات العامة بعيدة وما في إضاءة بالليل، البنات بيخافوا يروحوا لحالهم", "WASH;PROTECTION;ENERGY", "negative", 0),
    ("Q1", "A", "F", "زوجي مفقود من شهرين وما بعرف لوين أروح أسأل عنه", "PROTECTION;INFORMATION", "negative", 0),
    ("Q1", "C", "F", "نحتاج دواء ضغط لأمي، الصيدلية أسعارها غالية وما معنا مصاري", "HEALTH;CASH", "negative", 0),
    ("Q1", "B", "M", "الإيجار متأخر علينا ثلاث شهور وصاحب البيت بده يطلعنا", "SHELTER;CASH", "negative", 0),
    ("Q1", "A", "M", "أهم شي الأكل والمي، بعدين نحكي بالباقي", "FOOD;WASH", "negative", 0),
    ("Q1", "C", "F", "ابني عنده إعاقة حركية ومحتاج كرسي متحرك، الكرسي القديم انكسر", "HEALTH", "negative", 0),
    ("Q1", "B", "F", "حاليًا الوضع أحسن من قبل والحمد لله، بس نحتاج ملابس شتوية للأولاد", "SHELTER;APPRECIATION", "mixed", 0),
    ("Q1", "A", "M", "دورة تدريب مهني للشباب، الشباب قاعدين بدون شغل وهذا بخليهم يضيعوا", "LIVELIHOODS", "negative", 0),
    ("Q1", "C", "M", "لا شيء محدد", "OTHER", "neutral", 0),
    ("Q1", "B", "F", "قرطاسية وحقائب للمدرسة، المدرسة رجعت بس ما عنا إشي للأولاد", "EDUCATION", "negative", 0),
    ("Q1", "A", "F", "أنا حامل بالشهر السابع وما بقدر أوصل للعيادة، محتاجة متابعة", "HEALTH", "negative", 0),
    ("Q1", "C", "M", "كل شيء، الأكل والدواء والمكان، صرنا ما نعرف من وين نبدأ", "FOOD;HEALTH;SHELTER", "negative", 0),
    ("Q1", "B", "M", "الأوراق الثبوتية ضاعت ومحتاجين نطلع بدل ضائع عشان نسجل بالمساعدات", "PROTECTION;DISTRIBUTION", "negative", 0),
    ("Q1", "A", "F", "مكان آمن يلعب فيه الأولاد، الشارع خطر عليهم", "PROTECTION;MENTAL_HEALTH", "negative", 0),
    ("Q1", "C", "F", "نحتاج خزان مياه للبيت لأن المياه تيجي يوم بالأسبوع بس", "WASH", "negative", 0),
    ("Q1", "B", "M", "الدخل ما بكفي، بشتغل بالمياومة يومين بالأسبوع، لو في كاش بسد الديون", "LIVELIHOODS;CASH", "negative", 0),
    ("Q1", "A", "M", "بطانيات وحطب للتدفئة", "SHELTER;ENERGY", "neutral", 0),
    ("Q1", "C", "F", "علاج أسنان للأولاد، صار عندهم تسوس كتير وبيوجعهم", "HEALTH", "negative", 0),
    ("Q1", "B", "F", "ابني الكبير صار عصبي ومش طايق حدا، وأنا كمان تعبانة نفسيًا", "MENTAL_HEALTH", "negative", 0),
    ("Q1", "A", "M", "خضار وفواكه، صار لنا شهور عايشين على المعلبات", "FOOD;AID_QUALITY", "negative", 0),
    ("Q1", "C", "M", "نحتاج إنترنت حتى يكمل الأولاد دراستهم أونلاين", "EDUCATION;ENERGY", "neutral", 0),
    ("Q1", "B", "F", "مستلزمات لكبار السن، حماتي ما بتقدر تمشي وبدها حفاضات كبار", "HEALTH;WASH", "negative", 0),
    ("Q1", "A", "F", "شغل لإلي، أنا أرملة وعندي خمس أولاد وبعرف أخيط", "LIVELIHOODS", "neutral", 0),
    ("Q1", "C", "M", "بنتي عمرها 15 وفي ناس بيحكوا عن تزويجها بسبب الوضع، أنا رافض بس الضغط كبير", "PROTECTION;CASH", "negative", 1),
    ("Q1", "B", "M", "ترميم البيت، الجدار متشقق ويخاف ينهار على الأولاد", "SHELTER;PROTECTION", "negative", 0),
    ("Q1", "A", "M", "الأولوية للدواء ثم الطعام", "HEALTH;FOOD", "neutral", 0),
    ("Q1", "C", "F", "ماي نظيفة وحمام قريب، والله تعبنا", "WASH", "negative", 0),
    # Q2: feedback on the aid process
    ("Q2", "A", "F", "الطابور طويل كتير، وقفنا من الفجر للظهر بالشمس وفي ناس كبار بالعمر وقعوا", "DISTRIBUTION;HEALTH", "negative", 0),
    ("Q2", "B", "M", "ما حدا بلغنا بموعد التوزيع، عرفنا من الجيران بعد ما خلص", "INFORMATION;DISTRIBUTION", "negative", 0),
    ("Q2", "C", "F", "الموظفين كانوا محترمين كتير والتوزيع كان منظم، شكرًا إلكم", "STAFF_CONDUCT;DISTRIBUTION;APPRECIATION", "positive", 0),
    ("Q2", "A", "M", "الطرد ما بكفي عيلة من عشر أشخاص، لازم الكمية تكون حسب عدد الأفراد", "AID_QUALITY", "negative", 0),
    ("Q2", "B", "F", "في ناس بتاخد مرتين وناس ما بتاخد أبدًا، القوائم مش عادلة", "DISTRIBUTION", "negative", 0),
    ("Q2", "C", "M", "اتصلت على الرقم المجاني أكثر من مرة وما حدا رد", "INFORMATION", "negative", 0),
    ("Q2", "A", "F", "المعلبات اللي وصلتنا كانت منتهية الصلاحية", "AID_QUALITY;HEALTH", "negative", 0),
    ("Q2", "B", "M", "نقطة التوزيع بعيدة ومافي مواصلات، دفعت أجرة أكتر من قيمة الطرد", "DISTRIBUTION;CASH", "negative", 0),
    ("Q2", "C", "F", "واحد من المتطوعين طلب مني رقمي وصار يتصل علي بالليل ويقول بيضيفني عالقائمة إذا قابلته", "STAFF_CONDUCT;PROTECTION", "negative", 1),
    ("Q2", "A", "M", "الله يجزيكم الخير، المساعدة وصلت بوقتها", "APPRECIATION", "positive", 0),
    ("Q2", "B", "F", "يا ريت يكون في دور خاص للنساء وكبار السن وذوي الإعاقة", "DISTRIBUTION;PROTECTION", "neutral", 0),
    ("Q2", "C", "M", "بدنا نعرف شو المعايير اللي على أساسها بتختاروا العائلات", "INFORMATION;DISTRIBUTION", "neutral", 0),
    ("Q2", "A", "F", "الموظف صرخ علينا قدام الناس وحسسنا إنا بنشحد", "STAFF_CONDUCT", "negative", 0),
    ("Q2", "B", "M", "التوزيع ممتاز بس الكمية قليلة", "DISTRIBUTION;AID_QUALITY", "mixed", 0),
    ("Q2", "C", "F", "الرسائل النصية بتوصل متأخرة، يا ريت تبعتوا قبل بيومين", "INFORMATION", "neutral", 0),
    ("Q2", "A", "M", "واسطة، اللي بيعرف حدا بالمؤسسة بياخد أول", "DISTRIBUTION;STAFF_CONDUCT", "negative", 0),
    ("Q2", "B", "F", "أحسن إشي إنكم صرتوا تعطوا كوبونات بنشتري فيها اللي بدنا إياه", "CASH;APPRECIATION", "positive", 0),
    ("Q2", "C", "M", "الملابس اللي وزعتوها مقاساتها كبيرة كتير على الأولاد", "AID_QUALITY", "negative", 0),
    ("Q2", "A", "F", "ما في مكان نقدم فيه شكوى بدون ما حدا يعرف مين احنا", "INFORMATION;PROTECTION", "negative", 0),
    ("Q2", "B", "M", "تمام", "OTHER", "neutral", 0),
    ("Q2", "C", "F", "اسألونا قبل ما توزعوا، في أغراض بتوصلنا ما بنحتاجها وأغراض ضرورية ما بتوصل", "INFORMATION;AID_QUALITY", "negative", 0),
    ("Q2", "A", "M", "طلبوا مني أدفع 50 شيكل عشان يسجلوني بالكشف", "DISTRIBUTION;STAFF_CONDUCT;PROTECTION", "negative", 1),
    ("Q2", "B", "F", "المتطوعات كانوا لطيفين مع الأطفال وساعدوني أحمل الطرد للبيت", "STAFF_CONDUCT;APPRECIATION", "positive", 0),
    ("Q2", "C", "M", "التسجيل عن طريق الرابط صعب، مش كل الناس عندها إنترنت أو بتعرف تعبي", "DISTRIBUTION;INFORMATION", "negative", 0),
    ("Q2", "A", "F", "الحفاضات اللي بالطرد مقاس واحد بس، وأولادي أعمارهم مختلفة", "AID_QUALITY;WASH", "negative", 0),
    ("Q2", "B", "M", "الوقت بين التوزيعة والثانية طويل كتير، شهر ونص والطرد بيخلص بأسبوعين", "AID_QUALITY;FOOD", "negative", 0),
    ("Q2", "C", "F", "منيح إنكم بتسألونا، أول مرة حدا بيسأل عن رأينا", "INFORMATION;APPRECIATION", "positive", 0),
    ("Q2", "A", "M", "صار في عراك عند التوزيع لأنه ما في تنظيم وما في أرقام", "DISTRIBUTION;PROTECTION", "negative", 0),
    ("Q2", "B", "F", "بدنا جلسات دعم نفسي للأمهات مش بس للأولاد", "MENTAL_HEALTH", "neutral", 0),
    ("Q2", "C", "M", "شكرًا، بس لو تزيدوا المبلغ النقدي لأنه الأسعار نار", "CASH;APPRECIATION", "mixed", 0),
]


def main():
    DATA.mkdir(exist_ok=True)
    with open(DATA / "sample_responses.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["response_id", "question_id", "question_text", "site", "gender", "answer"])
        for i, (q, site, gender, answer, *_rest) in enumerate(ROWS, start=1):
            w.writerow([f"R{i:03d}", q, QUESTIONS[q], site, gender, answer])
    with open(DATA / "gold_labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["response_id", "themes", "sentiment", "needs_followup"])
        for i, (*_lead, themes, sentiment, followup) in enumerate(ROWS, start=1):
            w.writerow([f"R{i:03d}", themes, sentiment, followup])
    print(f"Wrote {len(ROWS)} synthetic answers to {DATA}")


if __name__ == "__main__":
    main()
